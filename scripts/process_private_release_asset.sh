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
if [[ "$TRANSCRIPTION_MODEL" != "large-v3-turbo" ]]; then
  echo "Release transcription requires the project-controlled model large-v3-turbo; got: $TRANSCRIPTION_MODEL" >&2
  exit 2
fi
if [[ "${AI_REVIEW_ENABLED,,}" == "true" ]]; then
  for name in VID_PIPELINE_REVIEW_API_KEY VID_PIPELINE_REVIEW_BASE_URL VID_PIPELINE_REVIEW_MODEL; do
    [[ -n "${!name:-}" ]] || { echo "Missing required review environment variable: $name" >&2; exit 2; }
  done
fi

mkdir -p /tmp/vid-pipeline-private
INPUT_MEDIA="/tmp/vid-pipeline-private/media-${RESULT_NUMBER}${MEDIA_SUFFIX}"
RUN_OUTPUT_ROOT="${RUN_OUTPUT_ROOT:-/tmp/vid-pipeline-private-output-${RESULT_NUMBER}}"
export INPUT_MEDIA RUN_OUTPUT_ROOT
rm -rf "$RUN_OUTPUT_ROOT"
rm -f "$INPUT_MEDIA" "$INPUT_MEDIA.part"
mkdir -p "$RUN_OUTPUT_ROOT"

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
        "User-Agent": "vid-pipeline-private-release-worker-v2",
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
        print(f"Private media verified: {size} bytes sha256:{actual}")
        break
    except (urllib.error.URLError, TimeoutError, RuntimeError) as exc:
        try:
            os.remove(temporary)
        except FileNotFoundError:
            pass
        if attempt == 3:
            raise
        print(f"asset download attempt {attempt + 1} failed: {exc}; retrying")
        time.sleep(2**attempt)
PY

args=(
  run-file "$INPUT_MEDIA"
  --name "private-${RESULT_NUMBER}"
  --output-root "$RUN_OUTPUT_ROOT"
  --profile "$TRANSCRIPTION_PROFILE"
  --model "$TRANSCRIPTION_MODEL"
  --language fa
  --device cpu
  --compute-type int8
  --no-editorial
)

if [[ "${DIARIZATION_ENABLED,,}" == "true" ]]; then
  args+=(--diarize --num-speakers "${NUM_SPEAKERS:-2}" --speaker-role-mode "${SPEAKER_ROLE_MODE:-generic}")
  [[ "${DIARIZATION_REQUIRED:-false}" == "true" ]] && args+=(--diarization-required)
fi

echo "Release asset ${RESULT_NUMBER}: starting ASR"
vid-pipeline "${args[@]}"
echo "Release asset ${RESULT_NUMBER}: ASR pipeline finished"

mkdir -p \
  "$COLLECTION_ROOT/md" \
  "$COLLECTION_ROOT/timestamped" \
  "$COLLECTION_ROOT/txt"

copy_one() {
  local source_name="$1"
  local target="$2"
  mapfile -t matches < <(find "$RUN_OUTPUT_ROOT" -type f -path "*/delivery/$source_name")
  if (( ${#matches[@]} != 1 )); then
    echo "Expected exactly one isolated delivery file for $source_name; found ${#matches[@]} under $RUN_OUTPUT_ROOT" >&2
    printf '  %s\n' "${matches[@]:-}" >&2
    exit 1
  fi
  cp "${matches[0]}" "$target"
}

copy_one transcript.md "$COLLECTION_ROOT/md/$RESULT_NUMBER.md"
copy_one transcript.timestamped.md "$COLLECTION_ROOT/timestamped/$RESULT_NUMBER.md"
copy_one transcript.txt "$COLLECTION_ROOT/txt/$RESULT_NUMBER.txt"

for path in \
  "$COLLECTION_ROOT/md/$RESULT_NUMBER.md" \
  "$COLLECTION_ROOT/timestamped/$RESULT_NUMBER.md" \
  "$COLLECTION_ROOT/txt/$RESULT_NUMBER.txt"; do
  [[ -s "$path" ]] || { echo "Expected base output is missing or empty: $path" >&2; exit 1; }
done

if [[ "${AI_REVIEW_ENABLED,,}" == "true" ]]; then
  mkdir -p \
    "$COLLECTION_ROOT/review/md" \
    "$COLLECTION_ROOT/review/timestamped" \
    "$COLLECTION_ROOT/review/txt"
  vid-review ai-collection "$COLLECTION_ROOT" "$RESULT_NUMBER"
  for path in \
    "$COLLECTION_ROOT/review/md/$RESULT_NUMBER.md" \
    "$COLLECTION_ROOT/review/timestamped/$RESULT_NUMBER.md" \
    "$COLLECTION_ROOT/review/txt/$RESULT_NUMBER.txt"; do
    [[ -s "$path" ]] || { echo "Expected review output is missing or empty: $path" >&2; exit 1; }
  done
  echo "Result $RESULT_NUMBER completed with AI review"
else
  echo "Result $RESULT_NUMBER completed without external AI review"
fi
