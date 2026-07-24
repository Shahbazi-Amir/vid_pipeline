"""Deterministic confidence scoring for transcript segments and review blocks."""

from __future__ import annotations

from typing import Any


def _clamp(value: float) -> float:
    return max(0.0, min(1.0, value))


def _label(score: float) -> str:
    if score >= 85:
        return "high"
    if score >= 70:
        return "medium"
    return "low"


def build_quality_report(raw_data: dict[str, Any], *, block_size: int = 5) -> dict[str, Any]:
    segment_scores: list[dict[str, Any]] = []
    for index, segment in enumerate(raw_data.get("segments") or []):
        probabilities = [
            float(item.get("probability", 1.0))
            for item in segment.get("words") or []
            if item.get("probability") is not None
        ]
        word_score = sum(probabilities) / len(probabilities) if probabilities else 0.65
        logprob = float(segment.get("avg_logprob", -1.0) or -1.0)
        logprob_score = _clamp(1.0 + logprob / 2.0)
        speech_score = _clamp(
            1.0 - float(segment.get("no_speech_prob", 0.0) or 0.0)
        )
        score = round(
            100 * (0.60 * word_score + 0.25 * logprob_score + 0.15 * speech_score),
            1,
        )
        segment_scores.append(
            {
                "segment_id": int(segment.get("id", index)),
                "start": round(float(segment.get("start", 0.0) or 0.0), 3),
                "end": round(float(segment.get("end", 0.0) or 0.0), 3),
                "score": score,
                "label": _label(score),
                "mean_word_confidence": round(word_score, 4),
                "avg_logprob": round(logprob, 4),
                "no_speech_probability": round(
                    float(segment.get("no_speech_prob", 0.0) or 0.0), 4
                ),
                "review_flags": list(segment.get("review_flags") or []),
            }
        )
    blocks: list[dict[str, Any]] = []
    for offset in range(0, len(segment_scores), max(1, block_size)):
        rows = segment_scores[offset : offset + max(1, block_size)]
        score = round(sum(item["score"] for item in rows) / len(rows), 1)
        blocks.append(
            {
                "block": len(blocks) + 1,
                "start": rows[0]["start"],
                "end": rows[-1]["end"],
                "segment_ids": [item["segment_id"] for item in rows],
                "score": score,
                "label": _label(score),
            }
        )
    overall = round(
        sum(item["score"] for item in segment_scores) / max(1, len(segment_scores)), 1
    )
    return {
        "schema_version": 1,
        "overall_score": overall,
        "overall_label": _label(overall),
        "segment_count": len(segment_scores),
        "segments": segment_scores,
        "blocks": blocks,
    }
