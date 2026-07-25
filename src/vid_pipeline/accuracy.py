"""Multi-pass ASR and conservative consensus for Persian transcripts."""
from __future__ import annotations

import difflib
import json
import os
import re
import shutil
import subprocess
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Iterable


class AccuracyError(RuntimeError):
    pass


@dataclass(slots=True)
class AccuracyConfig:
    mode: str = "balanced"  # off|fast|balanced|maximum
    model: str = ""
    device: str = "auto"
    compute_type: str = "auto"
    language: str = "fa"
    beam_size: int = 5
    targeted_beam_size: int = 10
    clip_context_seconds: float = 2.5
    max_targeted_segments: int = 120
    vote_similarity: float = 0.88
    minimum_score: float = 0.72
    low_confidence: float = 0.68
    judge_model: str = ""
    judge_base_url: str = "http://127.0.0.1:11434"
    whisperx_alignment: bool = False
    whisperx_model: str = ""
    diarization: bool = False
    diarization_model: str = "pyannote/speaker-diarization-community-1"
    huggingface_token: str = ""


@dataclass(slots=True)
class PassSpec:
    name: str
    model: str
    vad_filter: bool
    beam_size: int
    condition_on_previous_text: bool = False
    targeted: bool = False


PassRunner = Callable[[Path, PassSpec, str], dict[str, Any]]
SPACE = re.compile(r"\s+")
CLEAN = re.compile(r"[^\w\u0600-\u06FF]+", re.UNICODE)
PROTECTED = re.compile(
    r"[0-9۰-۹٠-٩]+|(?:صفر|یک|دو|سه|چهار|پنج|شش|هفت|هشت|نه|ده|صد|هزار|میلیون|میلیارد)|"
    r"(?:شهید|آقای|خانم|دکتر|مهندس|آیت(?:‌|\s)?الله|سردار|رئیس(?:‌|\s)?جمهور)\s+\S+"
)


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


def norm(text: str) -> str:
    value = str(text or "").translate(str.maketrans({"ي": "ی", "ى": "ی", "ك": "ک"}))
    return SPACE.sub(" ", value).strip()


def key(text: str) -> str:
    return CLEAN.sub(" ", norm(text)).strip().casefold()


def tokens(text: str) -> list[str]:
    return key(text).split()


def similarity(a: str, b: str) -> float:
    return difflib.SequenceMatcher(a=tokens(a), b=tokens(b), autojunk=False).ratio()


def confidence(segment: dict[str, Any]) -> float:
    values = [
        float(word["probability"])
        for word in segment.get("words") or []
        if isinstance(word, dict) and word.get("probability") is not None
    ]
    if values:
        return max(0.0, min(1.0, sum(values) / len(values)))
    return max(0.0, min(1.0, 1.0 + float(segment.get("avg_logprob", -1.0) or -1.0) / 2.0))


def runtime(device: str, compute: str) -> tuple[str, str]:
    try:
        import ctranslate2
    except ImportError as exc:
        raise AccuracyError("faster-whisper is not installed") from exc
    if device == "auto":
        try:
            device = "cuda" if ctranslate2.get_cuda_device_count() else "cpu"
        except Exception:
            device = "cpu"
    if compute == "auto":
        compute = "float16" if device == "cuda" else "int8"
    return device, compute


def run_whisper(path: Path, spec: PassSpec, hotwords: str, config: AccuracyConfig) -> dict[str, Any]:
    try:
        from faster_whisper import WhisperModel
    except ImportError as exc:
        raise AccuracyError("faster-whisper is not installed") from exc
    device, compute = runtime(config.device, config.compute_type)
    model = WhisperModel(spec.model, device=device, compute_type=compute)
    stream, info = model.transcribe(
        str(path),
        language=config.language,
        beam_size=spec.beam_size,
        vad_filter=spec.vad_filter,
        word_timestamps=True,
        condition_on_previous_text=spec.condition_on_previous_text,
        initial_prompt="رونویسی دقیق فارسی؛ نام‌ها، اعداد و عبارات عربی را بدون حدس ثبت کن.",
        hotwords=hotwords or None,
        repetition_penalty=1.08,
        no_repeat_ngram_size=3,
        hallucination_silence_threshold=2.0,
    )
    segments = []
    for index, segment in enumerate(stream):
        segments.append(
            {
                "id": int(getattr(segment, "id", index)),
                "start": float(segment.start),
                "end": float(segment.end),
                "text": str(segment.text).strip(),
                "avg_logprob": float(segment.avg_logprob),
                "compression_ratio": float(segment.compression_ratio),
                "no_speech_prob": float(segment.no_speech_prob),
                "words": [
                    {
                        "start": float(word.start),
                        "end": float(word.end),
                        "word": str(word.word),
                        "probability": float(word.probability),
                    }
                    for word in segment.words or []
                ],
            }
        )
    return {
        "model": spec.model,
        "language": getattr(info, "language", config.language),
        "duration": float(getattr(info, "duration", 0.0)),
        "segments": segments,
    }


def specs(config: AccuracyConfig, primary_model: str) -> list[PassSpec]:
    model = config.model or primary_model or "large-v3-turbo"
    if config.mode in {"off", "fast"}:
        return []
    result = [PassSpec("full-no-vad", model, False, max(5, config.beam_size))]
    if config.mode == "maximum":
        result.append(PassSpec("full-contextual-vad", model, True, max(8, config.beam_size), True))
    return result


def overlap(a: dict[str, Any], b: dict[str, Any]) -> float:
    return max(
        0.0,
        min(float(a.get("end", 0)), float(b.get("end", 0)))
        - max(float(a.get("start", 0)), float(b.get("start", 0))),
    )


def window_candidate(
    segment: dict[str, Any], result: dict[str, Any], name: str
) -> dict[str, Any] | None:
    rows = [row for row in result.get("segments") or [] if overlap(segment, row) > 0.05]
    rows.sort(key=lambda row: float(row.get("start", 0)))
    text = norm(" ".join(str(row.get("text") or "") for row in rows))
    if not text:
        return None
    return {
        "pass": name,
        "text": text,
        "normalized": key(text),
        "confidence": round(sum(confidence(row) for row in rows) / len(rows), 4),
    }


def select_consensus(candidates: list[dict[str, Any]], config: AccuracyConfig) -> dict[str, Any]:
    if not candidates:
        raise AccuracyError("no ASR candidates")
    for item in candidates:
        similarities = [similarity(item["text"], other["text"]) for other in candidates]
        item["votes"] = sum(value >= config.vote_similarity for value in similarities)
        item["agreement"] = round(sum(similarities) / len(similarities), 4)
        item["score"] = round(
            0.65 * (item["votes"] / len(candidates))
            + 0.25 * item["agreement"]
            + 0.10 * float(item.get("confidence", 0)),
            4,
        )
    winner = max(candidates, key=lambda item: (item["votes"], item["score"], item.get("confidence", 0)))
    primary = next((item for item in candidates if item["pass"] == "primary"), candidates[0])
    counts: dict[str, int] = {}
    for item in candidates:
        counts[item["normalized"]] = counts.get(item["normalized"], 0) + 1
    majority = counts.get(winner["normalized"], 0) >= 2
    protected = bool(PROTECTED.search(" ".join(item["text"] for item in candidates)))
    auto = (
        winner["votes"] >= 2
        and winner["score"] >= config.minimum_score
        and (majority or not protected)
    )
    selected = winner if auto else primary
    reasons = []
    if len({item["normalized"] for item in candidates}) > 1:
        reasons.append("multi_pass_disagreement")
    if float(selected.get("confidence", 0)) < config.low_confidence:
        reasons.append("low_consensus_confidence")
    if protected and not majority:
        reasons.append("protected_name_or_number_disagreement")
    return {
        "text": selected["text"],
        "selected_pass": selected["pass"],
        "score": selected["score"],
        "auto_accepted": auto,
        "requires_human": bool(reasons),
        "reasons": reasons,
        "candidates": candidates,
    }


def extract_clip(audio: Path, output: Path, start: float, end: float) -> str:
    if not shutil.which("ffmpeg"):
        return "ffmpeg_not_found"
    output.parent.mkdir(parents=True, exist_ok=True)
    command = [
        "ffmpeg",
        "-hide_banner",
        "-loglevel",
        "error",
        "-y",
        "-ss",
        f"{max(0, start):.3f}",
        "-i",
        str(audio),
        "-t",
        f"{max(0.2, end - max(0, start)):.3f}",
        "-ac",
        "1",
        "-ar",
        "16000",
        str(output),
    ]
    completed = subprocess.run(command, capture_output=True, text=True, check=False)
    return "" if completed.returncode == 0 else completed.stderr[-1000:] or "ffmpeg_failed"


def optional_enrichment(
    audio: Path, segments: list[dict[str, Any]], config: AccuracyConfig
) -> tuple[list[dict[str, Any]], list[str]]:
    warnings = []
    if config.whisperx_alignment:
        try:
            import whisperx

            device, _ = runtime(config.device, config.compute_type)
            waveform = whisperx.load_audio(str(audio))
            model, metadata = whisperx.load_align_model(
                language_code=config.language,
                device=device,
                model_name=config.whisperx_model or None,
            )
            aligned = whisperx.align(
                [
                    {"start": item["start"], "end": item["end"], "text": item["text"]}
                    for item in segments
                ],
                model,
                metadata,
                waveform,
                device,
                return_char_alignments=False,
            )
            for current, updated in zip(segments, aligned.get("segments") or []):
                current["start"] = float(updated.get("start", current["start"]))
                current["end"] = float(updated.get("end", current["end"]))
                current["words"] = updated.get("words") or []
                current["alignment"] = "whisperx"
        except Exception as exc:
            warnings.append(f"whisperx_alignment_failed: {type(exc).__name__}: {exc}")
    if config.diarization:
        token = config.huggingface_token or os.getenv("HUGGINGFACE_TOKEN", "")
        if not token:
            warnings.append("diarization_skipped_missing_huggingface_token")
        else:
            try:
                from pyannote.audio import Pipeline

                output = Pipeline.from_pretrained(config.diarization_model, token=token)(str(audio))
                annotation = (
                    getattr(output, "exclusive_speaker_diarization", None)
                    or getattr(output, "speaker_diarization", None)
                    or output
                )
                turns = [
                    (float(turn.start), float(turn.end), str(speaker))
                    for turn, _, speaker in annotation.itertracks(yield_label=True)
                ]
                for segment in segments:
                    best = max(
                        turns,
                        key=lambda turn: max(
                            0,
                            min(segment["end"], turn[1]) - max(segment["start"], turn[0]),
                        ),
                        default=None,
                    )
                    if best and max(
                        0,
                        min(segment["end"], best[1]) - max(segment["start"], best[0]),
                    ) > 0:
                        segment["speaker"] = best[2]
            except Exception as exc:
                warnings.append(f"diarization_failed: {type(exc).__name__}: {exc}")
    return segments, warnings


def stamp(seconds: float, vtt: bool = False) -> str:
    milliseconds = max(0, round(seconds * 1000))
    hours, milliseconds = divmod(milliseconds, 3_600_000)
    minutes, milliseconds = divmod(milliseconds, 60_000)
    secs, milliseconds = divmod(milliseconds, 1000)
    return f"{hours:02d}:{minutes:02d}:{secs:02d}{'.' if vtt else ','}{milliseconds:03d}"


def render_outputs(
    root: Path, data: dict[str, Any], disagreements: list[dict[str, Any]]
) -> dict[str, str]:
    output = root / "accuracy"
    output.mkdir(parents=True, exist_ok=True)
    segments = data["segments"]
    paths = {
        name: output / f"transcript.consensus.{extension}"
        for name, extension in [
            ("json", "json"),
            ("markdown", "md"),
            ("text", "txt"),
            ("srt", "srt"),
            ("vtt", "vtt"),
        ]
    }
    paths["disagreements"] = output / "disagreements.json"
    paths["json"].write_text(
        json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    paths["text"].write_text(
        "\n\n".join(segment["text"] for segment in segments).rstrip() + "\n",
        encoding="utf-8",
    )
    markdown = [
        "# متن اجماعی چندمرحله‌ای",
        "",
        "> فقط از کاندیدهای ASR انتخاب شده است.",
        "",
    ]
    for segment in segments:
        flags = ", ".join(segment.get("review_flags") or [])
        speaker = f" **{segment['speaker']}:**" if segment.get("speaker") else ""
        markdown += [
            f"[{stamp(segment['start'], True)} → {stamp(segment['end'], True)}]"
            + (f" ⚠️ `{flags}`" if flags else "")
            + speaker,
            segment["text"],
            "",
        ]
    paths["markdown"].write_text(
        "\n".join(markdown).rstrip() + "\n", encoding="utf-8"
    )
    paths["srt"].write_text(
        "\n\n".join(
            f"{index}\n{stamp(segment['start'])} --> {stamp(segment['end'])}\n{segment['text']}"
            for index, segment in enumerate(segments, 1)
        )
        + "\n",
        encoding="utf-8",
    )
    paths["vtt"].write_text(
        "WEBVTT\n\n"
        + "\n\n".join(
            f"{stamp(segment['start'], True)} --> {stamp(segment['end'], True)}\n{segment['text']}"
            for segment in segments
        )
        + "\n",
        encoding="utf-8",
    )
    paths["disagreements"].write_text(
        json.dumps({"schema_version": 1, "items": disagreements}, ensure_ascii=False, indent=2)
        + "\n",
        encoding="utf-8",
    )
    return {name: str(path) for name, path in paths.items()}


def build_accuracy_package(
    job_root: str | Path,
    *,
    config: AccuracyConfig | None = None,
    glossary_paths: Iterable[str | Path] = (),
    pass_runner: PassRunner | None = None,
) -> dict[str, Any]:
    config = config or AccuracyConfig()
    root = Path(job_root)
    raw_path = root / "raw" / "transcript.raw.json"
    audio = root / "audio" / "audio-16k-mono.wav"
    if config.mode not in {"off", "fast", "balanced", "maximum"}:
        raise AccuracyError(f"unsupported mode: {config.mode}")
    if not raw_path.exists():
        raise AccuracyError(f"missing raw transcript: {raw_path}")
    primary = json.loads(raw_path.read_text(encoding="utf-8"))
    primary_segments = primary.get("segments") or []
    if not primary_segments:
        raise AccuracyError("raw transcript has no segments")
    glossary_words = []
    for path in glossary_paths:
        payload = json.loads(Path(path).read_text(encoding="utf-8"))
        if isinstance(payload, dict):
            for canonical, aliases in payload.items():
                glossary_words.append(str(canonical))
                if isinstance(aliases, list):
                    glossary_words += [str(alias) for alias in aliases]
    hotwords = "، ".join(dict.fromkeys(glossary_words))[:1000]
    warnings = []
    passes = [("primary", primary)]
    if pass_runner is None:

        def runner(path: Path, pass_spec: PassSpec, words: str) -> dict[str, Any]:
            return run_whisper(path, pass_spec, words, config)

    else:
        runner = pass_runner
    if config.mode != "off" and audio.exists():
        for pass_spec in specs(config, str(primary.get("model") or "")):
            try:
                result = runner(audio, pass_spec, hotwords)
                passes.append((pass_spec.name, result))
                directory = root / "accuracy" / "passes"
                directory.mkdir(parents=True, exist_ok=True)
                (directory / f"{pass_spec.name}.json").write_text(
                    json.dumps(result, ensure_ascii=False, indent=2) + "\n",
                    encoding="utf-8",
                )
            except Exception as exc:
                warnings.append(f"{pass_spec.name}_failed: {type(exc).__name__}: {exc}")
    elif config.mode != "off":
        warnings.append("audio_missing_additional_passes_skipped")
    candidates: dict[int, list[dict[str, Any]]] = {}
    preliminary = {}
    for index, segment in enumerate(primary_segments):
        segment_id = int(segment.get("id", index))
        base = {
            "pass": "primary",
            "text": norm(segment.get("text") or "") or "[نامفهوم]",
            "normalized": key(segment.get("text") or ""),
            "confidence": round(confidence(segment), 4),
        }
        rows = [base]
        for name, result in passes[1:]:
            candidate = window_candidate(segment, result, name)
            if candidate:
                rows.append(candidate)
        candidates[segment_id] = rows
        preliminary[segment_id] = select_consensus(rows, config)
    target_ids = [
        int(segment.get("id", index))
        for index, segment in enumerate(primary_segments)
        if preliminary[int(segment.get("id", index))]["requires_human"]
        or segment.get("review_flags")
    ][: config.max_targeted_segments]
    if config.mode != "off" and audio.exists():
        target_spec = PassSpec(
            "targeted-high-beam",
            config.model or str(primary.get("model") or "large-v3-turbo"),
            False,
            config.targeted_beam_size,
            targeted=True,
        )
        by_id = {
            int(segment.get("id", index)): segment
            for index, segment in enumerate(primary_segments)
        }
        for segment_id in target_ids:
            segment = by_id[segment_id]
            clip = root / "accuracy" / "clips" / f"segment-{segment_id:04d}.wav"
            start = max(
                0, float(segment.get("start", 0)) - config.clip_context_seconds
            )
            end = float(segment.get("end", start)) + config.clip_context_seconds
            error = extract_clip(audio, clip, start, end)
            if error:
                warnings.append(f"clip_{segment_id}: {error}")
                continue
            try:
                result = runner(clip, target_spec, hotwords)
                text = norm(
                    " ".join(
                        str(row.get("text") or "")
                        for row in result.get("segments") or []
                    )
                )
                if text:
                    rows = result.get("segments") or []
                    candidates[segment_id].append(
                        {
                            "pass": target_spec.name,
                            "text": text,
                            "normalized": key(text),
                            "confidence": round(
                                sum(confidence(row) for row in rows) / max(1, len(rows)),
                                4,
                            ),
                        }
                    )
            except Exception as exc:
                warnings.append(
                    f"targeted_{segment_id}_failed: {type(exc).__name__}: {exc}"
                )
    consensus = []
    disagreements = []
    for index, segment in enumerate(primary_segments):
        segment_id = int(segment.get("id", index))
        decision = select_consensus(candidates[segment_id], config)
        flags = list(
            dict.fromkeys([*(segment.get("review_flags") or []), *decision["reasons"]])
        )
        row = {
            **segment,
            "id": segment_id,
            "text": decision["text"],
            "review_flags": flags,
            "consensus": decision,
        }
        consensus.append(row)
        if decision["requires_human"]:
            clip = root / "accuracy" / "clips" / f"segment-{segment_id:04d}.wav"
            disagreements.append(
                {
                    "segment_id": segment_id,
                    "start": float(segment.get("start", 0)),
                    "end": float(segment.get("end", 0)),
                    "reasons": decision["reasons"],
                    "selected_text": decision["text"],
                    "candidates": decision["candidates"],
                    "clip": str(clip) if clip.exists() else "",
                }
            )
    consensus, enrichment_warnings = optional_enrichment(audio, consensus, config)
    warnings += enrichment_warnings
    data = {
        "schema_version": 2,
        "language": primary.get("language") or config.language,
        "duration": primary.get("duration"),
        "model": "multi-pass-consensus",
        "source_models": [result.get("model") for _, result in passes],
        "mode": config.mode,
        "text": " ".join(segment["text"] for segment in consensus).strip(),
        "segments": consensus,
    }
    files = render_outputs(root, data, disagreements)
    manifest = {
        "schema_version": 1,
        "status": "accuracy_review_required"
        if disagreements
        else "accuracy_consensus_complete",
        "generated_at": now(),
        "mode": config.mode,
        "config": asdict(config),
        "primary_segment_count": len(primary_segments),
        "pass_count": len(passes),
        "targeted_segment_count": len(target_ids),
        "disagreement_count": len(disagreements),
        "files": files,
        "warnings": warnings,
        "external_reference_used": False,
    }
    manifest_path = root / "accuracy" / "manifest.json"
    manifest_path.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    manifest["files"]["manifest"] = str(manifest_path)
    state_path = root / "state.json"
    if state_path.exists():
        state = json.loads(state_path.read_text(encoding="utf-8"))
        state.setdefault("stages", {})["accuracy"] = {
            "status": "completed",
            "updated_at": now(),
            "output_paths": list(manifest["files"].values()),
            "details": {
                "mode": config.mode,
                "disagreement_count": len(disagreements),
            },
            "error": "",
        }
        state_path.write_text(
            json.dumps(state, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
    result_path = root / "result.json"
    result = (
        json.loads(result_path.read_text(encoding="utf-8"))
        if result_path.exists()
        else {}
    )
    result.update(
        {
            "accuracy_status": "completed",
            "accuracy_manifest": str(manifest_path),
            "accuracy_files": manifest["files"],
            "accuracy_human_verification": False,
        }
    )
    result_path.write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    return manifest


def edit_distance(a: list[str], b: list[str]) -> int:
    previous = list(range(len(b) + 1))
    for index, first in enumerate(a, 1):
        current = [index]
        for j, second in enumerate(b, 1):
            current.append(
                min(
                    current[-1] + 1,
                    previous[j] + 1,
                    previous[j - 1] + (first != second),
                )
            )
        previous = current
    return previous[-1]


def evaluate_text(reference: str, hypothesis: str) -> dict[str, Any]:
    reference_words, hypothesis_words = tokens(reference), tokens(hypothesis)
    reference_chars = list(key(reference).replace(" ", ""))
    hypothesis_chars = list(key(hypothesis).replace(" ", ""))
    word_errors = edit_distance(reference_words, hypothesis_words)
    character_errors = edit_distance(reference_chars, hypothesis_chars)
    return {
        "reference_words": len(reference_words),
        "hypothesis_words": len(hypothesis_words),
        "word_errors": word_errors,
        "wer": round(word_errors / max(1, len(reference_words)), 6),
        "reference_characters": len(reference_chars),
        "hypothesis_characters": len(hypothesis_chars),
        "character_errors": character_errors,
        "cer": round(character_errors / max(1, len(reference_chars)), 6),
    }


def evaluate_files(
    reference: str | Path,
    hypothesis: str | Path,
    output: str | Path | None = None,
) -> dict[str, Any]:
    result = {
        "schema_version": 1,
        "generated_at": now(),
        **evaluate_text(
            Path(reference).read_text(encoding="utf-8"),
            Path(hypothesis).read_text(encoding="utf-8"),
        ),
    }
    if output:
        Path(output).write_text(
            json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
    return result


__all__ = [
    "AccuracyConfig",
    "AccuracyError",
    "PassSpec",
    "build_accuracy_package",
    "evaluate_files",
    "evaluate_text",
    "key",
    "norm",
    "now",
    "render_outputs",
    "select_consensus",
]
