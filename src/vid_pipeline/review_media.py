"""Audio clipping and optional second-pass Whisper candidates."""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path
from typing import Any

from vid_pipeline.review_types import ReviewConfig, normalize_text


def extract_clip(audio: Path, destination: Path, start: float, end: float) -> str:
    if shutil.which("ffmpeg") is None:
        return "ffmpeg_not_found"
    destination.parent.mkdir(parents=True, exist_ok=True)
    command = [
        "ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
        "-ss", f"{start:.3f}", "-i", str(audio),
        "-t", f"{max(0.2, end - start):.3f}", "-ac", "1", "-ar", "16000",
        str(destination),
    ]
    result = subprocess.run(command, capture_output=True, text=True, check=False)
    return "" if result.returncode == 0 else result.stderr.strip()[-1000:] or "ffmpeg_failed"


def _mean(values: list[float]) -> float | None:
    return round(sum(values) / len(values), 4) if values else None


def retranscribe_items(
    items: list[dict[str, Any]],
    *,
    review_dir: Path,
    config: ReviewConfig,
    glossary_aliases: dict[str, str],
) -> list[str]:
    if not config.retranscribe_model:
        return []
    try:
        import ctranslate2
        from faster_whisper import WhisperModel
    except ImportError:
        return ["retranscription_skipped_faster_whisper_not_installed"]
    device = config.retranscribe_device
    if device == "auto":
        try:
            device = "cuda" if ctranslate2.get_cuda_device_count() > 0 else "cpu"
        except Exception:
            device = "cpu"
    compute = config.retranscribe_compute_type
    if compute == "auto":
        compute = "float16" if device == "cuda" else "int8"
    try:
        model = WhisperModel(config.retranscribe_model, device=device, compute_type=compute)
    except Exception as exc:
        return [f"retranscription_model_load_failed: {type(exc).__name__}: {exc}"]
    hotwords = "، ".join(sorted(set(glossary_aliases.values())))[:500]
    warnings: list[str] = []
    for item in items:
        clip = review_dir / str(item.get("clip") or "")
        if not item.get("clip") or not clip.exists():
            continue
        try:
            segments, _ = model.transcribe(
                str(clip), language="fa", beam_size=config.retranscribe_beam_size,
                word_timestamps=True, condition_on_previous_text=False,
                hotwords=hotwords or None,
            )
            texts: list[str] = []
            probabilities: list[float] = []
            for segment in segments:
                if segment.text.strip():
                    texts.append(segment.text.strip())
                probabilities.extend(float(word.probability) for word in segment.words or [])
            candidate = normalize_text(" ".join(texts))
            if candidate:
                item["retranscription"] = {
                    "model": config.retranscribe_model,
                    "text": candidate,
                    "mean_word_confidence": _mean(probabilities),
                }
        except Exception as exc:
            warnings.append(f"retranscription_failed_{item['id']}: {type(exc).__name__}: {exc}")
    return warnings
