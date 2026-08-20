"""Deterministic quality gate for online transcription jobs.

A worker reaching the end of ASR is not the same thing as producing a
trustworthy final transcript.  This module turns ASR confidence evidence into
an explicit pass/review-required decision so low-quality machine output cannot
be published as a completed delivery.
"""

from __future__ import annotations

import os
from dataclasses import asdict, dataclass
from typing import Any

from vid_pipeline.models import TranscriptDocument
from vid_pipeline.review_quality import build_quality_report


@dataclass(frozen=True, slots=True)
class QualityGatePolicy:
    min_overall_score: float = 70.0
    max_low_segment_ratio: float = 0.35
    max_flagged_segment_ratio: float = 0.60

    @classmethod
    def from_env(cls) -> "QualityGatePolicy":
        defaults = cls()
        policy = cls(
            min_overall_score=float(
                os.getenv(
                    "VID_PIPELINE_MIN_QUALITY_SCORE",
                    str(defaults.min_overall_score),
                )
            ),
            max_low_segment_ratio=float(
                os.getenv(
                    "VID_PIPELINE_MAX_LOW_SEGMENT_RATIO",
                    str(defaults.max_low_segment_ratio),
                )
            ),
            max_flagged_segment_ratio=float(
                os.getenv(
                    "VID_PIPELINE_MAX_FLAGGED_SEGMENT_RATIO",
                    str(defaults.max_flagged_segment_ratio),
                )
            ),
        )
        if not 0 <= policy.min_overall_score <= 100:
            raise ValueError("VID_PIPELINE_MIN_QUALITY_SCORE must be between 0 and 100")
        for name, value in (
            ("VID_PIPELINE_MAX_LOW_SEGMENT_RATIO", policy.max_low_segment_ratio),
            ("VID_PIPELINE_MAX_FLAGGED_SEGMENT_RATIO", policy.max_flagged_segment_ratio),
        ):
            if not 0 <= value <= 1:
                raise ValueError(f"{name} must be between 0 and 1")
        return policy


def _normalized_segments(
    raw_payload: dict[str, Any] | None,
    document: TranscriptDocument,
) -> list[dict[str, Any]]:
    source = list((raw_payload or {}).get("segments") or [])
    if not source:
        source = [segment.to_dict() for segment in document.segments]

    normalized: list[dict[str, Any]] = []
    for index, item in enumerate(source):
        confidence = item.get("confidence")
        words = list(item.get("words") or [])
        if not words and confidence is not None:
            words = [{"probability": float(confidence)}]
        flags = list(item.get("review_flags") or item.get("suspicious_flags") or [])
        avg_logprob = item.get("avg_logprob")
        if avg_logprob is None:
            # A document-only processor may provide a direct confidence score.
            # If it provides no confidence evidence at all, make the segment
            # conservatively low quality rather than silently accepting it.
            avg_logprob = 0.0 if confidence is not None else -2.0
        normalized.append(
            {
                "id": int(item.get("id", item.get("segment_id", index))),
                "start": float(item.get("start", 0.0) or 0.0),
                "end": float(item.get("end", 0.0) or 0.0),
                "text": str(item.get("text") or "").strip(),
                "avg_logprob": float(avg_logprob),
                "no_speech_prob": float(item.get("no_speech_prob", 0.0) or 0.0),
                "words": words,
                "review_flags": flags,
                "has_confidence_signal": bool(words) or item.get("avg_logprob") is not None,
            }
        )
    return normalized


def evaluate_transcript_quality(
    document: TranscriptDocument,
    raw_payload: dict[str, Any] | None = None,
    *,
    policy: QualityGatePolicy | None = None,
) -> dict[str, Any]:
    """Return a quality report with an explicit finalization decision."""

    policy = policy or QualityGatePolicy.from_env()
    quality_segments = _normalized_segments(raw_payload, document)
    report = build_quality_report({"segments": quality_segments})
    scored = list(report.get("segments") or [])
    segment_count = len(scored)
    low_count = sum(1 for item in scored if item.get("label") == "low")
    flagged_count = sum(1 for item in quality_segments if item.get("review_flags"))
    confidence_count = sum(
        1 for item in quality_segments if item.get("has_confidence_signal")
    )
    nonempty_count = sum(1 for item in quality_segments if item.get("text"))
    low_ratio = low_count / segment_count if segment_count else 1.0
    flagged_ratio = flagged_count / segment_count if segment_count else 1.0

    reasons: list[str] = []
    if segment_count == 0 or nonempty_count == 0 or not document.text.strip():
        reasons.append("empty_transcript")
    if segment_count and confidence_count == 0:
        reasons.append("missing_confidence_signals")
    if float(report.get("overall_score", 0.0)) < policy.min_overall_score:
        reasons.append("overall_score_below_threshold")
    if low_ratio > policy.max_low_segment_ratio:
        reasons.append("too_many_low_segments")
    if flagged_ratio > policy.max_flagged_segment_ratio:
        reasons.append("too_many_flagged_segments")

    report.update(
        {
            "valid": not reasons,
            "decision": "pass" if not reasons else "review_required",
            "gate_reasons": reasons,
            "thresholds": asdict(policy),
            "nonempty_segment_count": nonempty_count,
            "confidence_signal_segment_count": confidence_count,
            "low_segment_count": low_count,
            "low_segment_ratio": round(low_ratio, 6),
            "flagged_segment_count": flagged_count,
            "flagged_segment_ratio": round(flagged_ratio, 6),
        }
    )
    return report
