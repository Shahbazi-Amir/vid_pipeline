"""Render the canonical timecoded document into portable formats."""

from __future__ import annotations

import json
from pathlib import Path

from vid_pipeline.models import TranscriptDocument


def _stamp(value: float, separator: str = ".") -> str:
    millis = round(max(0.0, value) * 1000)
    hours, rem = divmod(millis, 3_600_000)
    minutes, rem = divmod(rem, 60_000)
    seconds, ms = divmod(rem, 1000)
    return f"{hours:02d}:{minutes:02d}:{seconds:02d}{separator}{ms:03d}"


def render_outputs(document: TranscriptDocument, final_dir: str | Path) -> dict[str, str]:
    root = Path(final_dir)
    root.mkdir(parents=True, exist_ok=True)
    paths = {
        "json": root / "transcript.final.timecoded.json",
        "timecoded_markdown": root / "transcript.final.timecoded.md",
        "srt": root / "transcript.final.srt",
        "vtt": root / "transcript.final.vtt",
        "markdown": root / "transcript.final.md",
        "text": root / "transcript.final.txt",
    }
    paths["json"].write_text(
        json.dumps(document.to_dict(), ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    timecoded = ["# متن نهایی زمان‌دار", ""]
    srt: list[str] = []
    vtt = ["WEBVTT", ""]
    paragraphs: list[str] = []
    for index, segment in enumerate(document.segments, 1):
        timecoded.extend([f"[{_stamp(segment.start)} → {_stamp(segment.end)}]", segment.text, ""])
        srt.extend(
            [
                str(index),
                f"{_stamp(segment.start, ',')} --> {_stamp(segment.end, ',')}",
                segment.text,
                "",
            ]
        )
        vtt.extend([f"{_stamp(segment.start)} --> {_stamp(segment.end)}", segment.text, ""])
        paragraphs.append(segment.text)
    paths["timecoded_markdown"].write_text("\n".join(timecoded).rstrip() + "\n", encoding="utf-8")
    paths["srt"].write_text("\n".join(srt).rstrip() + "\n", encoding="utf-8")
    paths["vtt"].write_text("\n".join(vtt).rstrip() + "\n", encoding="utf-8")
    paths["markdown"].write_text("\n\n".join(paragraphs).rstrip() + "\n", encoding="utf-8")
    paths["text"].write_text(document.text + "\n", encoding="utf-8")
    return {name: str(path) for name, path in paths.items()}
