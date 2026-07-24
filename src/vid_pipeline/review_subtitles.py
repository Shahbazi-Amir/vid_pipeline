"""Timestamp-preserving SRT and WebVTT rendering for review outputs."""

from __future__ import annotations

from typing import Any, Iterable

from vid_pipeline.review_types import normalize_text


def _timestamp(seconds: float, *, vtt: bool) -> str:
    milliseconds = max(0, round(float(seconds) * 1000))
    hours, remainder = divmod(milliseconds, 3_600_000)
    minutes, remainder = divmod(remainder, 60_000)
    secs, millis = divmod(remainder, 1000)
    separator = "." if vtt else ","
    return f"{hours:02d}:{minutes:02d}:{secs:02d}{separator}{millis:03d}"


def render_srt(segments: Iterable[dict[str, Any]], *, text_key: str = "text") -> str:
    blocks: list[str] = []
    for index, segment in enumerate(segments, start=1):
        text = normalize_text(str(segment.get(text_key) or segment.get("text") or ""))
        if not text:
            text = "[نامفهوم]"
        blocks.append(
            f"{index}\n{_timestamp(float(segment.get('start', 0.0) or 0.0), vtt=False)} --> "
            f"{_timestamp(float(segment.get('end', 0.0) or 0.0), vtt=False)}\n{text}"
        )
    return "\n\n".join(blocks).rstrip() + "\n"


def render_vtt(segments: Iterable[dict[str, Any]], *, text_key: str = "text") -> str:
    blocks = ["WEBVTT", ""]
    for segment in segments:
        text = normalize_text(str(segment.get(text_key) or segment.get("text") or ""))
        if not text:
            text = "[نامفهوم]"
        blocks.append(
            f"{_timestamp(float(segment.get('start', 0.0) or 0.0), vtt=True)} --> "
            f"{_timestamp(float(segment.get('end', 0.0) or 0.0), vtt=True)}\n{text}"
        )
    return "\n\n".join(blocks).rstrip() + "\n"
