"""Lossless, time-aligned transcript package generated before editorial review."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Iterable
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


class PreReviewError(RuntimeError):
    """Raised when a pre-review package cannot be generated safely."""


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _timestamp(seconds: float, *, vtt: bool = False) -> str:
    milliseconds = max(0, round(float(seconds) * 1000))
    hours, remainder = divmod(milliseconds, 3_600_000)
    minutes, remainder = divmod(remainder, 60_000)
    secs, millis = divmod(remainder, 1000)
    separator = "." if vtt else ","
    return f"{hours:02d}:{minutes:02d}:{secs:02d}{separator}{millis:03d}"


def _display_timestamp(seconds: float) -> str:
    return _timestamp(seconds, vtt=True)


def _normalized_segments(raw: dict[str, Any]) -> list[dict[str, Any]]:
    normalized: list[dict[str, Any]] = []
    for index, source in enumerate(raw.get("segments") or []):
        if not isinstance(source, dict):
            continue
        segment = dict(source)
        start = float(segment.get("start", 0.0) or 0.0)
        end = max(start, float(segment.get("end", start) or start))
        words: list[dict[str, Any]] = []
        for item in segment.get("words") or []:
            if not isinstance(item, dict):
                continue
            word = dict(item)
            word_start = float(word.get("start", start) or start)
            word_end = max(word_start, float(word.get("end", word_start) or word_start))
            word.update(start=word_start, end=word_end)
            words.append(word)
        segment.update(
            id=int(segment.get("id", index)),
            start=start,
            end=end,
            duration=round(end - start, 3),
            text=str(segment.get("text") or "").strip(),
            speaker=str(segment.get("speaker") or "").strip(),
            words=words,
            review_flags=[str(value) for value in segment.get("review_flags") or []],
        )
        normalized.append(segment)
    return normalized


def _render_txt(raw: dict[str, Any], segments: list[dict[str, Any]]) -> str:
    lines = [
        "نسخه کامل زمان‌دار پیش از بازبینی",
        "=================================",
        "",
        "این فایل مستقیماً از خروجی خام تشخیص گفتار ساخته شده است.",
        "هیچ جمله‌ای حذف، خلاصه یا بازنویسی نشده است.",
        "زمان‌ها هم‌ترازی تخمینی مدل Whisper هستند و جای تأیید انسانی با صوت را نمی‌گیرند.",
        "",
        f"زبان: {raw.get('language') or ''}",
        f"مدل: {raw.get('model') or ''}",
        f"مدت صوت: {float(raw.get('duration', 0.0) or 0.0):.3f} ثانیه",
        f"تعداد بخش‌ها: {len(segments)}",
        "",
    ]
    for segment in segments:
        start = _display_timestamp(segment["start"])
        end = _display_timestamp(segment["end"])
        lines.extend(
            [
                f"[SEGMENT {segment['id']:04d}] [{start} --> {end}]",
                f"مدت بخش: {segment['duration']:.3f} ثانیه",
            ]
        )
        if segment.get("speaker"):
            lines.append(f"گوینده: {segment['speaker']}")
        if segment.get("avg_logprob") is not None:
            lines.append(f"avg_logprob: {float(segment['avg_logprob']):.6f}")
        if segment.get("no_speech_prob") is not None:
            lines.append(f"no_speech_prob: {float(segment['no_speech_prob']):.6f}")
        if segment.get("compression_ratio") is not None:
            lines.append(f"compression_ratio: {float(segment['compression_ratio']):.6f}")
        flags = segment.get("review_flags") or []
        lines.append("پرچم‌های بازبینی: " + (", ".join(flags) if flags else "ندارد"))
        lines.extend(["متن:", segment.get("text") or "[نامفهوم]", ""])
        words = segment.get("words") or []
        if words:
            lines.append("کلمات زمان‌دار:")
            for word in words:
                probability = word.get("probability")
                confidence = "" if probability is None else f" | confidence={float(probability):.4f}"
                lines.append(
                    f"  {_display_timestamp(word['start'])} --> "
                    f"{_display_timestamp(word['end'])} | {str(word.get('word') or '').strip()}"
                    f"{confidence}"
                )
            lines.append("")
        lines.extend(["-" * 80, ""])
    return "\n".join(lines).rstrip() + "\n"


def _render_markdown(raw: dict[str, Any], segments: list[dict[str, Any]]) -> str:
    lines = [
        "# نسخه کامل زمان‌دار پیش از بازبینی",
        "",
        "> این خروجی مستقیماً از Whisper ساخته شده و هیچ حذف، خلاصه‌سازی یا بازنویسی ندارد.  ",
        "> زمان‌ها تخمینی‌اند و برای انتشار حساس باید با صوت بررسی شوند.",
        "",
        f"- زبان: `{raw.get('language') or ''}`",
        f"- مدل: `{raw.get('model') or ''}`",
        f"- مدت صوت: `{float(raw.get('duration', 0.0) or 0.0):.3f}` ثانیه",
        f"- تعداد بخش‌ها: `{len(segments)}`",
        "",
    ]
    for segment in segments:
        lines.extend(
            [
                f"## بخش {segment['id']} — "
                f"{_display_timestamp(segment['start'])} تا {_display_timestamp(segment['end'])}",
                "",
                f"**مدت:** `{segment['duration']:.3f}` ثانیه  ",
            ]
        )
        if segment.get("speaker"):
            lines.append(f"**گوینده:** {segment['speaker']}  ")
        metrics = []
        for key in ("avg_logprob", "no_speech_prob", "compression_ratio"):
            if segment.get(key) is not None:
                metrics.append(f"`{key}={float(segment[key]):.6f}`")
        if metrics:
            lines.append("**شاخص‌ها:** " + "، ".join(metrics) + "  ")
        flags = segment.get("review_flags") or []
        lines.append("**پرچم‌ها:** " + ("، ".join(f"`{item}`" for item in flags) if flags else "ندارد"))
        lines.extend(["", segment.get("text") or "[نامفهوم]", ""])
        words = segment.get("words") or []
        if words:
            lines.extend(
                [
                    "<details>",
                    "<summary>نمایش زمان و confidence تک‌تک کلمات</summary>",
                    "",
                    "| شروع | پایان | کلمه | confidence |",
                    "|---:|---:|---|---:|",
                ]
            )
            for word in words:
                probability = word.get("probability")
                confidence = "" if probability is None else f"{float(probability):.4f}"
                token = str(word.get("word") or "").strip().replace("|", "\\|")
                lines.append(
                    f"| `{_display_timestamp(word['start'])}` | "
                    f"`{_display_timestamp(word['end'])}` | {token} | {confidence} |"
                )
            lines.extend(["", "</details>", ""])
    return "\n".join(lines).rstrip() + "\n"


def _render_srt(segments: Iterable[dict[str, Any]]) -> str:
    blocks: list[str] = []
    for index, segment in enumerate(segments, start=1):
        text = str(segment.get("text") or "").strip() or "[نامفهوم]"
        blocks.append(
            f"{index}\n{_timestamp(segment['start'])} --> {_timestamp(segment['end'])}\n{text}"
        )
    return "\n\n".join(blocks).rstrip() + "\n"


def _render_vtt(segments: Iterable[dict[str, Any]]) -> str:
    blocks = ["WEBVTT", ""]
    for segment in segments:
        text = str(segment.get("text") or "").strip() or "[نامفهوم]"
        blocks.append(
            f"{_timestamp(segment['start'], vtt=True)} --> "
            f"{_timestamp(segment['end'], vtt=True)}\n{text}"
        )
    return "\n\n".join(blocks).rstrip() + "\n"


def _update_state(job_root: Path, outputs: list[Path], manifest: dict[str, Any]) -> None:
    state_path = job_root / "state.json"
    if not state_path.exists():
        return
    state = json.loads(state_path.read_text(encoding="utf-8"))
    state.setdefault("stages", {})["pre_review"] = {
        "status": "completed",
        "updated_at": _utc_now(),
        "output_paths": [str(path.resolve()) for path in outputs],
        "details": {
            "segment_count": manifest["segment_count"],
            "word_count": manifest["word_count"],
            "sha256": {str(path.resolve()): _sha256(path) for path in outputs},
        },
        "error": "",
    }
    state["updated_at"] = _utc_now()
    state_path.write_text(json.dumps(state, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _update_result(job_root: Path, manifest_path: Path, files: dict[str, str]) -> None:
    result_path = job_root / "result.json"
    if not result_path.exists():
        return
    result = json.loads(result_path.read_text(encoding="utf-8"))
    result["pre_review_status"] = "completed"
    result["pre_review_manifest"] = str(manifest_path)
    result["pre_review_files"] = files
    result_path.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def build_pre_review_package(job_root: str | Path) -> dict[str, Any]:
    """Create a lossless, detailed, time-aligned package from raw Whisper JSON."""

    root = Path(job_root)
    raw_path = root / "raw" / "transcript.raw.json"
    if not raw_path.exists():
        raise PreReviewError(f"Raw Whisper transcript does not exist: {raw_path}")
    try:
        raw = json.loads(raw_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise PreReviewError(f"Raw Whisper transcript is invalid JSON: {raw_path}") from exc
    if not isinstance(raw, dict):
        raise PreReviewError("Raw Whisper transcript must contain a JSON object.")
    segments = _normalized_segments(raw)
    if not segments:
        raise PreReviewError("Raw Whisper transcript has no segments.")

    output_dir = root / "pre_review"
    output_dir.mkdir(parents=True, exist_ok=True)
    text_path = output_dir / "transcript.pre-review.txt"
    markdown_path = output_dir / "transcript.pre-review.md"
    json_path = output_dir / "transcript.pre-review.json"
    srt_path = output_dir / "transcript.pre-review.srt"
    vtt_path = output_dir / "transcript.pre-review.vtt"
    manifest_path = output_dir / "manifest.json"

    text_path.write_text(_render_txt(raw, segments), encoding="utf-8")
    markdown_path.write_text(_render_markdown(raw, segments), encoding="utf-8")
    json_payload = {
        "schema_version": 1,
        "status": "pre_review_complete",
        "generated_at": _utc_now(),
        "source": "raw_whisper_audio_only",
        "external_reference_used": False,
        "timing_accuracy": "model_aligned_estimate",
        "transcription": {**raw, "segments": segments},
    }
    json_path.write_text(json.dumps(json_payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    srt_path.write_text(_render_srt(segments), encoding="utf-8")
    vtt_path.write_text(_render_vtt(segments), encoding="utf-8")

    word_count = sum(len(segment.get("words") or []) for segment in segments)
    files = {
        "text": str(text_path),
        "markdown": str(markdown_path),
        "json": str(json_path),
        "srt": str(srt_path),
        "vtt": str(vtt_path),
    }
    manifest = {
        "schema_version": 1,
        "status": "pre_review_complete",
        "generated_at": _utc_now(),
        "source": "raw_whisper_audio_only",
        "external_reference_used": False,
        "timing_accuracy": "model_aligned_estimate",
        "segment_count": len(segments),
        "word_count": word_count,
        "source_raw_json": str(raw_path),
        "source_raw_sha256": _sha256(raw_path),
        "files": files,
    }
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    outputs = [text_path, markdown_path, json_path, srt_path, vtt_path, manifest_path]
    _update_state(root, outputs, manifest)
    _update_result(root, manifest_path, {**files, "manifest": str(manifest_path)})
    return manifest


__all__ = ["PreReviewError", "build_pre_review_package"]
