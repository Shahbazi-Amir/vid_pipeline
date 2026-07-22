"""Speech recognition with faster-whisper."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from vid_pipeline.errors import ExternalToolError

DEFAULT_INITIAL_PROMPT = ""


@dataclass(slots=True)
class TranscriptionConfig:
    model: str = "small"
    device: str = "auto"
    compute_type: str = "auto"
    language: str = "fa"
    beam_size: int = 5
    vad_filter: bool = True
    word_timestamps: bool = True
    condition_on_previous_text: bool = False
    initial_prompt: str = DEFAULT_INITIAL_PROMPT


def format_timestamp(seconds: float) -> str:
    milliseconds = max(0, round(seconds * 1000))
    hours, remainder = divmod(milliseconds, 3_600_000)
    minutes, remainder = divmod(remainder, 60_000)
    secs, millis = divmod(remainder, 1000)
    if hours:
        return f"{hours:02d}:{minutes:02d}:{secs:02d}.{millis:03d}"
    return f"{minutes:02d}:{secs:02d}.{millis:03d}"


def _load_whisper():
    try:
        import ctranslate2
        from faster_whisper import WhisperModel
    except ImportError as exc:
        raise ExternalToolError(
            "faster-whisper is not installed. Run: pip install -e '.[whisper]'"
        ) from exc
    return ctranslate2, WhisperModel


def resolve_runtime(device: str, compute_type: str) -> tuple[str, str]:
    ctranslate2, _ = _load_whisper()
    selected_device = device
    if selected_device == "auto":
        try:
            selected_device = "cuda" if ctranslate2.get_cuda_device_count() > 0 else "cpu"
        except Exception:
            selected_device = "cpu"
    selected_compute = compute_type
    if selected_compute == "auto":
        selected_compute = "float16" if selected_device == "cuda" else "int8"
    return selected_device, selected_compute


def suspicious_reasons(segment: dict[str, Any]) -> list[str]:
    reasons: list[str] = []
    text = str(segment.get("text", "")).strip()
    if float(segment.get("avg_logprob", 0.0)) < -1.0:
        reasons.append("low_log_probability")
    if float(segment.get("no_speech_prob", 0.0)) > 0.6:
        reasons.append("possible_non_speech")
    words = segment.get("words") or []
    probabilities = [
        float(item.get("probability", 1.0))
        for item in words
        if item.get("probability") is not None
    ]
    if probabilities and sum(probabilities) / len(probabilities) < 0.55:
        reasons.append("low_word_confidence")
    normalized = re.sub(r"\s+", " ", text)
    tokens = normalized.split()
    if len(tokens) >= 12 and len(set(tokens)) / len(tokens) < 0.35:
        reasons.append("possible_repetition")
    if not text:
        reasons.append("empty_text")
    return reasons


def transcribe_audio(
    audio_path: str | Path,
    output_json: str | Path,
    output_markdown: str | Path,
    config: TranscriptionConfig | None = None,
) -> dict[str, Any]:
    config = config or TranscriptionConfig()
    source = Path(audio_path)
    if not source.exists():
        raise ExternalToolError(f"Audio file does not exist: {source}")
    _, WhisperModel = _load_whisper()
    device, compute_type = resolve_runtime(config.device, config.compute_type)
    try:
        model = WhisperModel(config.model, device=device, compute_type=compute_type)
        segments_iter, info = model.transcribe(
            str(source),
            language=config.language,
            beam_size=config.beam_size,
            vad_filter=config.vad_filter,
            word_timestamps=config.word_timestamps,
            condition_on_previous_text=config.condition_on_previous_text,
            initial_prompt=config.initial_prompt or None,
        )
        segments: list[dict[str, Any]] = []
        all_text: list[str] = []
        for item in segments_iter:
            words = []
            for word in item.words or []:
                words.append(
                    {
                        "start": float(word.start),
                        "end": float(word.end),
                        "word": word.word,
                        "probability": float(word.probability),
                    }
                )
            segment = {
                "id": int(item.id),
                "start": float(item.start),
                "end": float(item.end),
                "text": item.text.strip(),
                "avg_logprob": float(item.avg_logprob),
                "compression_ratio": float(item.compression_ratio),
                "no_speech_prob": float(item.no_speech_prob),
                "words": words,
            }
            segment["review_flags"] = suspicious_reasons(segment)
            segments.append(segment)
            if segment["text"]:
                all_text.append(segment["text"])
        result = {
            "schema_version": 1,
            "language": info.language,
            "language_probability": float(info.language_probability),
            "duration": float(info.duration),
            "model": config.model,
            "device": device,
            "compute_type": compute_type,
            "text": " ".join(all_text).strip(),
            "segments": segments,
        }
    except Exception as exc:
        if isinstance(exc, ExternalToolError):
            raise
        raise ExternalToolError(f"Transcription failed: {exc}") from exc

    json_path = Path(output_json)
    md_path = Path(output_markdown)
    json_path.parent.mkdir(parents=True, exist_ok=True)
    md_path.parent.mkdir(parents=True, exist_ok=True)
    json_path.write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    lines = ["# متن خام زمان‌دار", ""]
    for segment in result["segments"]:
        flags = ", ".join(segment["review_flags"])
        suffix = f" ⚠️ `{flags}`" if flags else ""
        lines.append(
            f"[{format_timestamp(segment['start'])} → {format_timestamp(segment['end'])}]{suffix}"
        )
        lines.append(segment["text"] or "[نامفهوم]")
        lines.append("")
    md_path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")
    return result
