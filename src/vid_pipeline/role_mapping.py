"""Deterministic and conservative speaker-role attribution.

Speaker diarization answers *who spoke when*.  This module separately decides
whether two already-separated speakers can safely be called host/teacher.
"""

from __future__ import annotations

from typing import Any

ROLE_ALIASES = {
    "host": "مجری",
    "teacher": "استاد",
    "مجری": "مجری",
    "استاد": "استاد",
}

# Deliberately omit weak discourse markers such as «یعنی».  They are common in
# explanatory speech and previously biased the heuristic toward the teacher.
QUESTION_MARKERS = (
    "؟",
    "?",
    "چرا",
    "چطور",
    "چگونه",
    "آیا",
    "چی",
    "چه ",
    "می شود",
    "می‌شود",
    "ممکن است",
)


def _median(values: list[float]) -> float:
    ordered = sorted(values)
    if not ordered:
        return 0.0
    middle = len(ordered) // 2
    if len(ordered) % 2:
        return float(ordered[middle])
    return float((ordered[middle - 1] + ordered[middle]) / 2)


def _relative_advantage(preferred: float, other: float) -> float:
    """Return a bounded pairwise advantage in approximately [-1, 1]."""

    scale = max(abs(preferred), abs(other), 1e-9)
    return (preferred - other) / scale


def role_features(segments: list[dict[str, Any]], speaker: str) -> dict[str, Any]:
    items = [row for row in segments if str(row.get("speaker") or "") == speaker]
    word_counts = [
        int(row.get("aligned_word_count") or len(str(row.get("text") or "").split()))
        for row in items
    ]
    durations = [
        max(0.0, float(row.get("end", 0.0)) - float(row.get("start", 0.0)))
        for row in items
    ]
    question_count = sum(
        any(marker in str(row.get("text") or "") for marker in QUESTION_MARKERS)
        for row in items
    )
    count = max(1, len(items))
    total_words = sum(word_counts)
    total_duration = sum(durations)
    return {
        "utterance_count": len(items),
        "question_count": question_count,
        "question_fraction": question_count / count,
        "mean_words": total_words / count,
        "median_words": _median([float(value) for value in word_counts]),
        "mean_duration": total_duration / count,
        "median_duration": _median(durations),
        "short_turn_fraction": sum(
            words <= 12 or duration <= 6.0
            for words, duration in zip(word_counts, durations)
        )
        / count,
        "long_turn_fraction": sum(
            words >= 40 or duration >= 18.0
            for words, duration in zip(word_counts, durations)
        )
        / count,
        "total_words": total_words,
        "total_duration": total_duration,
    }


def map_roles_with_diagnostics(
    segments: list[dict[str, Any]],
    mode: str,
    overrides: dict[str, str] | None = None,
    threshold: float = 0.72,
) -> tuple[dict[str, dict[str, Any]], dict[str, Any]]:
    speakers = sorted({str(row.get("speaker")) for row in segments if row.get("speaker")})
    mapping = {
        speaker: {"role": "", "confidence": 0.0, "source": "unresolved"}
        for speaker in speakers
    }
    features = {speaker: role_features(segments, speaker) for speaker in speakers}
    diagnostics: dict[str, Any] = {
        "mode": mode,
        "status": "unresolved",
        "source": "none",
        "confidence": 0.0,
        "threshold": threshold,
        "features": features,
        "host_score_margin": 0.0,
    }

    manual_speakers: list[str] = []
    for speaker, requested_role in (overrides or {}).items():
        if speaker not in mapping:
            continue
        role = ROLE_ALIASES.get(requested_role, requested_role)
        mapping[speaker] = {"role": role, "confidence": 1.0, "source": "manual"}
        manual_speakers.append(speaker)

    if manual_speakers:
        if mode == "host-teacher" and len(speakers) == 2 and len(manual_speakers) == 1:
            manual_speaker = manual_speakers[0]
            other = next(speaker for speaker in speakers if speaker != manual_speaker)
            role = mapping[manual_speaker]["role"]
            if role in {"مجری", "استاد"}:
                mapping[other] = {
                    "role": "استاد" if role == "مجری" else "مجری",
                    "confidence": 1.0,
                    "source": "manual-complement",
                }
        diagnostics.update(
            {"status": "resolved_manual", "source": "manual", "confidence": 1.0}
        )
        return mapping, diagnostics

    if mode != "host-teacher":
        diagnostics["status"] = "unresolved_mode"
        return mapping, diagnostics
    if len(speakers) != 2:
        diagnostics["status"] = "unresolved_speaker_count"
        return mapping, diagnostics

    left, right = speakers
    a, b = features[left], features[right]

    # Positive margin means LEFT is more host-like.  Question frequency is only
    # one weak signal because an expert can ask rhetorical questions.  Shorter
    # turns and lower explanatory airtime/word volume carry more pairwise weight.
    margin = (
        0.10 * (a["question_fraction"] - b["question_fraction"])
        + 0.20 * (a["short_turn_fraction"] - b["short_turn_fraction"])
        + 0.20 * _relative_advantage(b["mean_words"], a["mean_words"])
        + 0.20 * _relative_advantage(b["mean_duration"], a["mean_duration"])
        + 0.10 * (b["long_turn_fraction"] - a["long_turn_fraction"])
        + 0.10 * _relative_advantage(b["total_words"], a["total_words"])
        + 0.10 * _relative_advantage(b["total_duration"], a["total_duration"])
    )
    host = left if margin >= 0 else right
    teacher = right if host == left else left
    separation = abs(margin)
    confidence = min(0.95, 0.5 + separation * 1.8)

    features[left]["host_score"] = round(0.5 + margin / 2, 6)
    features[right]["host_score"] = round(0.5 - margin / 2, 6)
    features[left]["teacher_score"] = round(1.0 - features[left]["host_score"], 6)
    features[right]["teacher_score"] = round(1.0 - features[right]["host_score"], 6)
    diagnostics.update(
        {
            "confidence": round(confidence, 3),
            "host_score_margin": round(separation, 6),
        }
    )

    if confidence < threshold:
        diagnostics.update(
            {"status": "unresolved_low_confidence", "source": "heuristic-v2"}
        )
        return mapping, diagnostics

    mapping[host] = {
        "role": "مجری",
        "confidence": round(confidence, 3),
        "source": "heuristic-v2",
    }
    mapping[teacher] = {
        "role": "استاد",
        "confidence": round(confidence, 3),
        "source": "heuristic-v2",
    }
    diagnostics.update(
        {
            "status": "resolved_heuristic",
            "source": "heuristic-v2",
            "host_speaker": host,
            "teacher_speaker": teacher,
        }
    )
    return mapping, diagnostics


def map_roles(
    segments: list[dict[str, Any]],
    mode: str,
    overrides: dict[str, str] | None = None,
    threshold: float = 0.72,
) -> dict[str, dict[str, Any]]:
    mapping, _ = map_roles_with_diagnostics(segments, mode, overrides, threshold)
    return mapping
