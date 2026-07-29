"""Timestamp-aware merge and conservative boundary de-duplication."""

from __future__ import annotations

import re
from difflib import SequenceMatcher
from typing import Any


def normalize_persian(text: str) -> str:
    translation = str.maketrans({"ي": "ی", "ك": "ک", "ۀ": "ه", "ة": "ه"})
    return re.sub(r"[^\w\u0600-\u06ff]+", " ", text.translate(translation)).strip().lower()


def _overlap_words(left: str, right: str, *, limit: int = 24) -> int:
    a = normalize_persian(left).split()
    b = normalize_persian(right).split()
    for size in range(min(limit, len(a), len(b)), 2, -1):
        if SequenceMatcher(None, a[-size:], b[:size]).ratio() >= 0.9:
            return size
    return 0


def merge_chunk_segments(chunks: list[dict[str, Any]]) -> list[dict[str, Any]]:
    indexes = [int(chunk["chunk_index"]) for chunk in chunks]
    if indexes != list(range(len(chunks))):
        raise ValueError("chunks must be present once and in continuous order")
    merged: list[dict[str, Any]] = []
    for chunk in chunks:
        offset = float(chunk["start"])
        segments = chunk.get("segments")
        if not isinstance(segments, list):
            raise ValueError("chunk segments must be a list")
        for original in segments:
            segment = dict(original)
            segment["start"] = float(segment["start"]) + offset
            segment["end"] = float(segment["end"]) + offset
            if segment["start"] < 0 or segment["end"] < segment["start"]:
                raise ValueError("invalid segment timestamps")
            if merged:
                previous = merged[-1]
                in_boundary = segment["start"] <= previous["end"] + 20.0
                words = _overlap_words(str(previous.get("text", "")), str(segment.get("text", "")))
                if in_boundary and words:
                    current_words = str(segment.get("text", "")).split()
                    segment["text"] = " ".join(current_words[words:]).strip()
                    if not segment["text"]:
                        continue
                segment["start"] = max(segment["start"], previous["start"])
            segment["id"] = len(merged)
            merged.append(segment)
    if any(a["start"] > b["start"] for a, b in zip(merged, merged[1:])):
        raise ValueError("merged timestamps are not monotonic")
    return merged
