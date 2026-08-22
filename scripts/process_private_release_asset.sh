#!/usr/bin/env bash
set -euo pipefail

required=(
  PRIVATE_MEDIA_REPO PRIVATE_MEDIA_TOKEN ASSET_ID EXPECTED_SIZE MEDIA_SUFFIX
  RESULT_NUMBER COLLECTION_ROOT DIARIZATION_ENABLED
)
for name in "${required[@]}"; do
  [[ -n "${!name:-}" ]] || { echo "Missing required environment variable: $name" >&2; exit 2; }
done

AI_REVIEW_ENABLED="${AI_REVIEW_ENABLED:-false}"
TRANSCRIPTION_MODEL="${TRANSCRIPTION_MODEL:-large-v3-turbo}"
TRANSCRIPTION_PROFILE="${TRANSCRIPTION_PROFILE:-balanced}"
AUDIO_PROFILE="${AUDIO_PROFILE:-safe}"
if [[ "$TRANSCRIPTION_MODEL" != "large-v3-turbo" ]]; then
  echo "Release transcription requires the project-controlled model large-v3-turbo; got: $TRANSCRIPTION_MODEL" >&2
  exit 2
fi
if [[ "${AI_REVIEW_ENABLED,,}" == "true" ]]; then
  echo "Release base transcription intentionally does not run AI review. Review must be a separate auditable phase." >&2
  exit 2
fi
if [[ "${DIARIZATION_ENABLED,,}" == "true" ]]; then
  echo "Release base transcription intentionally defers diarization to the review/enrichment phase." >&2
  exit 2
fi

mkdir -p /tmp/vid-pipeline-private
INPUT_MEDIA="/tmp/vid-pipeline-private/media-${RESULT_NUMBER}${MEDIA_SUFFIX}"
RUN_OUTPUT_ROOT="${RUN_OUTPUT_ROOT:-/tmp/vid-pipeline-private-output-${RESULT_NUMBER}}"
WORK_ROOT="$RUN_OUTPUT_ROOT/work"
export INPUT_MEDIA RUN_OUTPUT_ROOT WORK_ROOT
rm -rf "$RUN_OUTPUT_ROOT"
rm -f "$INPUT_MEDIA" "$INPUT_MEDIA.part"
mkdir -p "$WORK_ROOT"

cleanup() {
  rm -rf "$RUN_OUTPUT_ROOT"
  rm -f "$INPUT_MEDIA" "$INPUT_MEDIA.part"
}
trap cleanup EXIT

echo "Release asset ${RESULT_NUMBER}: downloading id=${ASSET_ID} size=${EXPECTED_SIZE} model=${TRANSCRIPTION_MODEL} profile=${TRANSCRIPTION_PROFILE}"
python - <<'PY'
import hashlib
import os
import time
import urllib.error
import urllib.request

repo = os.environ["PRIVATE_MEDIA_REPO"].strip()
token = os.environ["PRIVATE_MEDIA_TOKEN"].strip()
asset_id = int(os.environ["ASSET_ID"])
expected_size = int(os.environ["EXPECTED_SIZE"])
expected_digest = os.environ.get("EXPECTED_DIGEST", "").strip()
target = os.environ["INPUT_MEDIA"]

request = urllib.request.Request(
    f"https://api.github.com/repos/{repo}/releases/assets/{asset_id}",
    headers={
        "Accept": "application/octet-stream",
        "Authorization": f"Bearer {token}",
        "X-GitHub-Api-Version": "2022-11-28",
        "User-Agent": "vid-pipeline-private-release-worker-v3",
    },
)
temporary = target + ".part"
for attempt in range(4):
    try:
        digest = hashlib.sha256()
        size = 0
        with urllib.request.urlopen(request, timeout=120) as response, open(temporary, "wb") as output:
            while chunk := response.read(1024 * 1024):
                output.write(chunk)
                digest.update(chunk)
                size += len(chunk)
        if size != expected_size:
            raise RuntimeError(f"downloaded private asset size mismatch: {size} != {expected_size}")
        actual = digest.hexdigest()
        if expected_digest.startswith("sha256:") and expected_digest != f"sha256:{actual}":
            raise RuntimeError("downloaded private asset digest mismatch")
        os.replace(temporary, target)
        print(f"Private media verified: {size} bytes sha256:{actual}", flush=True)
        break
    except (urllib.error.URLError, TimeoutError, RuntimeError) as exc:
        try:
            os.remove(temporary)
        except FileNotFoundError:
            pass
        if attempt == 3:
            raise
        print(f"asset download attempt {attempt + 1} failed: {exc}; retrying", flush=True)
        time.sleep(2**attempt)
PY

# Resolve the integrity-pinned project model to a local directory and forbid
# any runtime Hugging Face lookup/fallback.
export HF_HUB_OFFLINE=1
export HF_HUB_DISABLE_TELEMETRY=1
export TRANSFORMERS_OFFLINE=1
MODEL_PATH="$(PYTHONPATH=src python - <<'PY'
from vid_pipeline.asr_model import AsrModelManager
result = AsrModelManager().provision("large-v3-turbo")
if not result.path.is_dir():
    raise SystemExit("project ASR model cache is not materialized")
print(result.path.resolve())
PY
)"
export MODEL_PATH AUDIO_PROFILE
[[ -d "$MODEL_PATH" ]] || { echo "Resolved ASR model path is unavailable: $MODEL_PATH" >&2; exit 2; }
echo "Release asset ${RESULT_NUMBER}: using local ASR model path $MODEL_PATH"

echo "Release asset ${RESULT_NUMBER}: starting single-pass base transcription"
PYTHONPATH=src python - <<'PY'
import json
import os
import time
from pathlib import Path

from vid_pipeline.audio import normalize_audio
from vid_pipeline.clean import clean_transcript
from vid_pipeline.media import require_decodable_audio
from vid_pipeline.transcribe import TranscriptionConfig, transcribe_audio

media = Path(os.environ["INPUT_MEDIA"])
work = Path(os.environ["WORK_ROOT"])
model_path = os.environ["MODEL_PATH"]
asset_name = os.environ.get("ASSET_NAME", media.name)
audio_profile = os.environ.get("AUDIO_PROFILE", "safe")

source = require_decodable_audio(media)
print(
    "BASE_STAGE stage=probe status=completed "
    f"duration_seconds={source.get('duration_seconds')} input_type={source.get('input_type')}",
    flush=True,
)

audio = work / "audio.wav"
audio_quality = work / "audio-quality.json"
started = time.monotonic()
normalize_audio(media, audio, overwrite=True, profile=audio_profile, quality_path=audio_quality)
normalize_seconds = time.monotonic() - started
print(f"BASE_STAGE stage=normalize status=completed seconds={normalize_seconds:.3f}", flush=True)

raw_json = work / "transcript.raw.json"
raw_md = work / "transcript.raw.md"
started = time.monotonic()
raw = transcribe_audio(
    audio,
    raw_json,
    raw_md,
    TranscriptionConfig(
        model=model_path,
        device="cpu",
        compute_type="int8",
        language="fa",
        beam_size=5,
        vad_filter=True,
        word_timestamps=True,
        condition_on_previous_text=False,
    ),
)
asr_wall_seconds = time.monotonic() - started
print(
    "BASE_STAGE stage=asr status=completed "
    f"seconds={asr_wall_seconds:.3f} segments={len(raw.get('segments') or [])} "
    f"duration_seconds={raw.get('duration')}",
    flush=True,
)

machine_md = work / "transcript.machine.md"
machine_txt = work / "transcript.machine.txt"
started = time.monotonic()
clean = clean_transcript(
    raw_json,
    machine_md,
    machine_txt,
    title=asset_name,
    source_url="",
)
clean_seconds = time.monotonic() - started
print(f"BASE_STAGE stage=clean status=completed seconds={clean_seconds:.3f}", flush=True)

metrics = {
    "schema_version": 1,
    "mode": "single_pass_base_transcription",
    "asset_name": asset_name,
    "input_duration_seconds": source.get("duration_seconds"),
    "raw_duration_seconds": raw.get("duration"),
    "segment_count": len(raw.get("segments") or []),
    "normalize_seconds": round(normalize_seconds, 6),
    "asr_wall_seconds": round(asr_wall_seconds, 6),
    "asr_timing": raw.get("timing") or {},
    "clean_seconds": round(clean_seconds, 6),
    "model_path": model_path,
    "model_name": "large-v3-turbo",
    "device": "cpu",
    "compute_type": "int8",
    "review_status": "pending_review",
    "clean": clean,
}
(work / "metrics.json").write_text(
    json.dumps(metrics, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
)
PY

echo "Release asset ${RESULT_NUMBER}: base transcription finished"

mkdir -p \
  "$COLLECTION_ROOT/md" \
  "$COLLECTION_ROOT/timestamped" \
  "$COLLECTION_ROOT/txt" \
  "$COLLECTION_ROOT/json" \
  "$COLLECTION_ROOT/metrics"

cp "$WORK_ROOT/transcript.machine.md" "$COLLECTION_ROOT/md/$RESULT_NUMBER.md"
cp "$WORK_ROOT/transcript.raw.md" "$COLLECTION_ROOT/timestamped/$RESULT_NUMBER.md"
cp "$WORK_ROOT/transcript.machine.txt" "$COLLECTION_ROOT/txt/$RESULT_NUMBER.txt"
cp "$WORK_ROOT/transcript.raw.json" "$COLLECTION_ROOT/json/$RESULT_NUMBER.json"
cp "$WORK_ROOT/metrics.json" "$COLLECTION_ROOT/metrics/$RESULT_NUMBER.json"

for path in \
  "$COLLECTION_ROOT/md/$RESULT_NUMBER.md" \
  "$COLLECTION_ROOT/timestamped/$RESULT_NUMBER.md" \
  "$COLLECTION_ROOT/txt/$RESULT_NUMBER.txt" \
  "$COLLECTION_ROOT/json/$RESULT_NUMBER.json" \
  "$COLLECTION_ROOT/metrics/$RESULT_NUMBER.json"; do
  [[ -s "$path" ]] || { echo "Expected base output is missing or empty: $path" >&2; exit 1; }
done

echo "Result $RESULT_NUMBER completed: single-pass base transcript ready; review deferred"
