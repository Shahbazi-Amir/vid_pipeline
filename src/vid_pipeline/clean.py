"""Deterministic cleanup for ordered speech-to-text segments."""

from __future__ import annotations

import json
import re
from collections.abc import Iterable
from pathlib import Path
from typing import Any

_ARABIC_TO_PERSIAN = str.maketrans({"ي": "ی", "ى": "ی", "ك": "ک", "ۀ": "هٔ"})
_SPACE_RE = re.compile(r"\s+")
_REPEAT_TOKEN_RE = re.compile(r"\b([\w\u0600-\u06FF]+)(?:\s+\1){2,}\b", re.IGNORECASE)
_TERMINAL_PUNCTUATION = (".", "!", "?", "؟", "؛", ":")


def normalize_text(text: str) -> str:
    """Normalize Persian/Arabic characters and whitespace without changing meaning."""
    value = str(text or "").translate(_ARABIC_TO_PERSIAN)
    value = value.replace("\u200f", "").replace("\u200e", "")
    value = _SPACE_RE.sub(" ", value).strip()
    value = re.sub(r"\s+([،؛:.!?؟])", r"\1", value)
    value = re.sub(r"([،؛:.!?؟])(?!\s|$)", r"\1 ", value)
    value = _REPEAT_TOKEN_RE.sub(r"\1", value)
    return value.strip()


def _normalized_key(text: str) -> str:
    return re.sub(r"[^\w\u0600-\u06FF]+", " ", normalize_text(text)).strip().casefold()


def ordered_segment_texts(segments: Iterable[dict[str, Any]]) -> list[str]:
    """Return cleaned segment texts in original order, removing only exact adjacent repeats."""
    output: list[str] = []
    previous_key = ""
    for segment in segments:
        text = normalize_text(str(segment.get("text", "")))
        if not text:
            text = "[نامفهوم]"
        key = _normalized_key(text)
        if key and key == previous_key:
            continue
        output.append(text)
        previous_key = key
    return output


def build_paragraphs(texts: Iterable[str], max_words: int = 90) -> list[str]:
    """Group ordered segments into readable paragraphs without reordering content."""
    if max_words < 20:
        raise ValueError("max_words must be at least 20")
    paragraphs: list[str] = []
    current: list[str] = []
    word_count = 0

    def flush() -> None:
        nonlocal current, word_count
        if current:
            paragraphs.append(normalize_text(" ".join(current)))
            current = []
            word_count = 0

    for text in texts:
        words = text.split()
        if current and word_count + len(words) > max_words:
            flush()
        current.append(text)
        word_count += len(words)
        if text.endswith(_TERMINAL_PUNCTUATION) and word_count >= max_words // 2:
            flush()
    flush()
    return [item for item in paragraphs if item]


def render_final_markdown(
    *,
    title: str,
    source_url: str,
    paragraphs: Iterable[str],
    language: str,
) -> str:
    """Render the machine-cleaned transcript as standalone Markdown."""
    safe_title = normalize_text(title) or "متن ویدئو"
    lines = [f"# {safe_title}", ""]
    if source_url:
        lines.extend([f"**منبع:** {source_url}", ""])
    lines.extend(
        [
            "> این متن به‌صورت خودکار از صوت استخراج و پاک‌سازی شده است. ترتیب گفت‌وگو حفظ شده، زمان‌نماها حذف شده‌اند و تکرارهای آشکار اصلاح شده‌اند. برای انتشار حساس، تطبیق انسانی با صوت توصیه می‌شود.",
            "",
        ]
    )
    for paragraph in paragraphs:
        lines.extend([paragraph, ""])
    lines.extend(["---", "", f"زبان تشخیص‌داده‌شده: `{language or 'unknown'}`", ""])
    return "\n".join(lines).rstrip() + "\n"


def clean_transcript(
    raw_json: str | Path,
    output_markdown: str | Path,
    output_text: str | Path,
    *,
    title: str = "",
    source_url: str = "",
    max_words: int = 90,
) -> dict[str, Any]:
    """Create final Markdown and plain-text files from a Whisper JSON result."""
    source = Path(raw_json)
    data = json.loads(source.read_text(encoding="utf-8"))
    segments = data.get("segments") or []
    texts = ordered_segment_texts(segments)
    paragraphs = build_paragraphs(texts, max_words=max_words)
    language = str(data.get("language") or "")

    md_path = Path(output_markdown)
    txt_path = Path(output_text)
    md_path.parent.mkdir(parents=True, exist_ok=True)
    txt_path.parent.mkdir(parents=True, exist_ok=True)
    md_path.write_text(
        render_final_markdown(
            title=title or str(data.get("title") or ""),
            source_url=source_url,
            paragraphs=paragraphs,
            language=language,
        ),
        encoding="utf-8",
    )
    txt_path.write_text("\n\n".join(paragraphs).rstrip() + "\n", encoding="utf-8")
    return {
        "segments_in": len(segments),
        "segments_out": len(texts),
        "paragraphs": len(paragraphs),
        "language": language,
        "markdown": str(md_path),
        "text": str(txt_path),
    }
