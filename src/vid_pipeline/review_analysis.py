"""Suspicious-span detection, glossary suggestions and editorial auditing."""

from __future__ import annotations

import difflib
import json
import re
from collections.abc import Iterable
from pathlib import Path
from typing import Any

from vid_pipeline.review_types import (
    NUMBER_RE,
    NUMBER_WORD_RE,
    ReviewConfig,
    ReviewError,
    normalize_text,
    normalized_key,
    tokenize,
)

ARABIC_DIACRITICS_RE = re.compile(r"[\u064b-\u065f\u0670\u06d6-\u06ed]")
MIXED_SCRIPT_RE = re.compile(r"(?=.*[A-Za-z])(?=.*[\u0600-\u06FF])")
REPEAT_CHAR_RE = re.compile(r"([\u0600-\u06FFA-Za-z])\1{2,}")
NAME_MARKER_RE = re.compile(
    r"(?:شهید|آقای|خانم|دکتر|مهندس|حجت(?:‌|\s)?الاسلام|آیت(?:‌|\s)?الله|سردار|استاندار|رئیس(?:‌|\s)?جمهور)\s+([\u0600-\u06FF‌\-]+(?:\s+[\u0600-\u06FF‌\-]+){0,3})"
)
QURAN_MARKERS = {
    "قال",
    "الله",
    "الذین",
    "رب",
    "ربنا",
    "ان",
    "انا",
    "فی",
    "الارض",
    "الآخره",
    "الاخرة",
    "صدق",
    "صدق‌الله",
}


def load_glossaries(paths: Iterable[str | Path]) -> dict[str, str]:
    aliases: dict[str, str] = {}
    for raw_path in paths:
        path = Path(raw_path)
        payload = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(payload, dict) and isinstance(payload.get("entries"), list):
            payload = payload["entries"]
        entries: list[tuple[str, list[str]]] = []
        if isinstance(payload, dict):
            for canonical, values in payload.items():
                values = [values] if isinstance(values, str) else values
                if isinstance(values, list):
                    entries.append((str(canonical), [str(item) for item in values]))
        elif isinstance(payload, list):
            for item in payload:
                if isinstance(item, dict) and item.get("canonical"):
                    values = item.get("aliases") or []
                    values = [values] if isinstance(values, str) else values
                    entries.append(
                        (str(item["canonical"]), [str(value) for value in values])
                    )
        else:
            raise ReviewError(f"Unsupported glossary structure: {path}")
        for canonical, values in entries:
            canonical = normalize_text(canonical)
            aliases[normalized_key(canonical)] = canonical
            for alias in values:
                key = normalized_key(alias)
                if key:
                    aliases[key] = canonical
    return aliases


def glossary_suggestions(
    text: str, aliases: dict[str, str]
) -> tuple[list[dict[str, str]], str]:
    suggestions: list[dict[str, str]] = []
    proposed = normalize_text(text)
    for alias, canonical in sorted(
        aliases.items(), key=lambda item: len(item[0]), reverse=True
    ):
        if not alias or alias == normalized_key(canonical):
            continue
        pattern = re.compile(
            r"(?<![\w\u0600-\u06FF])"
            + re.escape(alias).replace(r"\ ", r"\s+")
            + r"(?![\w\u0600-\u06FF])",
            re.IGNORECASE,
        )
        replaced = pattern.sub(canonical, proposed)
        if replaced != proposed:
            suggestions.append({"observed": alias, "canonical": canonical})
            proposed = replaced
    return suggestions, proposed


def _mean(values: list[float]) -> float | None:
    return round(sum(values) / len(values), 4) if values else None


def analyze_segments(
    raw_data: dict[str, Any],
    *,
    config: ReviewConfig | None = None,
    glossary_aliases: dict[str, str] | None = None,
) -> list[dict[str, Any]]:
    config = config or ReviewConfig()
    glossary_aliases = glossary_aliases or {}
    items: list[dict[str, Any]] = []
    for index, segment in enumerate(raw_data.get("segments") or []):
        text = normalize_text(str(segment.get("text") or "")) or "[نامفهوم]"
        reasons = set(str(item) for item in segment.get("review_flags") or [])
        avg_logprob = float(segment.get("avg_logprob", 0.0) or 0.0)
        no_speech = float(segment.get("no_speech_prob", 0.0) or 0.0)
        if avg_logprob < config.segment_logprob_threshold:
            reasons.add("low_log_probability")
        if no_speech > config.no_speech_threshold:
            reasons.add("possible_non_speech")
        words = list(segment.get("words") or [])
        confidences = [
            float(row["probability"])
            for row in words
            if row.get("probability") is not None
        ]
        low_words = [
            {
                "word": normalize_text(str(row.get("word") or "")),
                "start": float(row.get("start", segment.get("start", 0.0)) or 0.0),
                "end": float(row.get("end", segment.get("end", 0.0)) or 0.0),
                "probability": round(float(row.get("probability", 0.0) or 0.0), 4),
            }
            for row in words
            if float(row.get("probability", 1.0) or 1.0)
            < config.confidence_threshold
        ]
        if low_words:
            reasons.add("low_word_confidence")
        numbers = NUMBER_RE.findall(text) + NUMBER_WORD_RE.findall(text)
        if numbers:
            reasons.add("number_or_percentage")
        names = [normalize_text(value) for value in NAME_MARKER_RE.findall(text)]
        if names:
            reasons.add("person_or_title")
        tokens = {normalized_key(token) for token in text.split()}
        if ARABIC_DIACRITICS_RE.search(text) or len(tokens & QURAN_MARKERS) >= 2:
            reasons.add("arabic_or_quranic_phrase")
        if MIXED_SCRIPT_RE.search(text):
            reasons.add("mixed_script")
        if REPEAT_CHAR_RE.search(text):
            reasons.add("repeated_character")
        suggestions, proposed = glossary_suggestions(text, glossary_aliases)
        if suggestions:
            reasons.add("glossary_match")
        if not reasons:
            continue
        segment_id = int(segment.get("id", index))
        items.append(
            {
                "id": f"segment-{segment_id:04d}",
                "segment_id": segment_id,
                "segment_index": index,
                "start": round(float(segment.get("start", 0.0) or 0.0), 3),
                "end": round(float(segment.get("end", 0.0) or 0.0), 3),
                "source_text": text,
                "proposed_text": proposed,
                "required": True,
                "reasons": sorted(reasons),
                "avg_logprob": round(avg_logprob, 4),
                "no_speech_probability": round(no_speech, 4),
                "mean_word_confidence": _mean(confidences),
                "minimum_word_confidence": (
                    round(min(confidences), 4) if confidences else None
                ),
                "low_confidence_words": low_words,
                "numbers": numbers,
                "names": names,
                "glossary_suggestions": suggestions,
                "decision": "pending",
                "replacement": "",
                "clip": "",
                "retranscription": None,
            }
        )
    return items


def audit_transcript_changes(machine_text: str, final_text: str) -> dict[str, Any]:
    machine = tokenize(machine_text)
    final = tokenize(final_text)
    matcher = difflib.SequenceMatcher(a=machine, b=final, autojunk=False)
    changes: list[dict[str, Any]] = []
    deleted = inserted = replaced = 0
    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        if tag == "equal":
            continue
        deleted += i2 - i1 if tag == "delete" else 0
        inserted += j2 - j1 if tag == "insert" else 0
        replaced += max(i2 - i1, j2 - j1) if tag == "replace" else 0
        if len(changes) < 200:
            changes.append(
                {
                    "operation": tag,
                    "machine_range": [i1, i2],
                    "final_range": [j1, j2],
                    "machine_text": " ".join(machine[i1:i2]),
                    "final_text": " ".join(final[j1:j2]),
                }
            )
    machine_numbers = NUMBER_RE.findall(machine_text) + NUMBER_WORD_RE.findall(machine_text)
    final_numbers = NUMBER_RE.findall(final_text) + NUMBER_WORD_RE.findall(final_text)
    ratio = round(len(final) / max(1, len(machine)), 4)
    similarity = round(matcher.ratio(), 4)
    warnings: list[str] = []
    if ratio < 0.80:
        warnings.append("large_content_deletion")
    if ratio > 1.25:
        warnings.append("large_content_addition")
    if machine_numbers != final_numbers:
        warnings.append("numbers_changed")
    if similarity < 0.65:
        warnings.append("low_sequence_similarity")
    return {
        "machine_tokens": len(machine),
        "final_tokens": len(final),
        "length_ratio": ratio,
        "sequence_similarity": similarity,
        "deleted_tokens": deleted,
        "inserted_tokens": inserted,
        "replaced_tokens": replaced,
        "machine_numbers": machine_numbers,
        "final_numbers": final_numbers,
        "warnings": warnings,
        "changes": changes,
    }
