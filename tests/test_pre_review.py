from __future__ import annotations

import json
from pathlib import Path

import pytest

from vid_pipeline.pre_review import PreReviewError, build_pre_review_package


def _make_job(tmp_path: Path) -> Path:
    job = tmp_path / "job"
    (job / "raw").mkdir(parents=True)
    raw = {
        "schema_version": 1,
        "language": "fa",
        "duration": 4.2,
        "model": "large-v3-turbo",
        "segments": [
            {
                "id": 3,
                "start": 0.21,
                "end": 2.1,
                "text": "سلام دنیا",
                "avg_logprob": -0.25,
                "compression_ratio": 1.1,
                "no_speech_prob": 0.01,
                "review_flags": ["person_or_title"],
                "words": [
                    {"start": 0.21, "end": 0.8, "word": " سلام", "probability": 0.91},
                    {"start": 0.8, "end": 1.4, "word": " دنیا", "probability": 0.73},
                ],
            },
            {
                "id": 4,
                "start": 2.1,
                "end": 4.2,
                "text": "خداحافظ",
                "avg_logprob": -0.4,
                "compression_ratio": 1.0,
                "no_speech_prob": 0.02,
                "review_flags": [],
                "words": [],
            },
        ],
    }
    (job / "raw" / "transcript.raw.json").write_text(
        json.dumps(raw, ensure_ascii=False), encoding="utf-8"
    )
    (job / "state.json").write_text(
        json.dumps({"stages": {}, "schema_version": 2}), encoding="utf-8"
    )
    (job / "result.json").write_text(
        json.dumps({"status": "completed", "review_status": "machine_only"}),
        encoding="utf-8",
    )
    return job


def test_builds_lossless_time_aligned_outputs(tmp_path: Path) -> None:
    job = _make_job(tmp_path)
    manifest = build_pre_review_package(job)
    assert manifest["segment_count"] == 2
    assert manifest["word_count"] == 2
    assert manifest["external_reference_used"] is False

    text = (job / "pre_review" / "transcript.pre-review.txt").read_text(encoding="utf-8")
    assert "[SEGMENT 0003] [00:00:00.210 --> 00:00:02.100]" in text
    assert "00:00:00.210 --> 00:00:00.800 | سلام | confidence=0.9100" in text
    assert "هیچ جمله‌ای حذف، خلاصه یا بازنویسی نشده است" in text

    payload = json.loads(
        (job / "pre_review" / "transcript.pre-review.json").read_text(encoding="utf-8")
    )
    assert payload["transcription"]["segments"][0]["text"] == "سلام دنیا"
    assert payload["transcription"]["segments"][0]["words"][1]["probability"] == 0.73

    srt = (job / "pre_review" / "transcript.pre-review.srt").read_text(encoding="utf-8")
    assert "00:00:00,210 --> 00:00:02,100" in srt
    vtt = (job / "pre_review" / "transcript.pre-review.vtt").read_text(encoding="utf-8")
    assert vtt.startswith("WEBVTT")

    state = json.loads((job / "state.json").read_text(encoding="utf-8"))
    assert state["stages"]["pre_review"]["status"] == "completed"
    result = json.loads((job / "result.json").read_text(encoding="utf-8"))
    assert result["pre_review_status"] == "completed"
    assert result["pre_review_files"]["text"].endswith("transcript.pre-review.txt")


def test_rejects_missing_or_empty_raw_transcript(tmp_path: Path) -> None:
    with pytest.raises(PreReviewError, match="does not exist"):
        build_pre_review_package(tmp_path / "missing")

    job = tmp_path / "empty"
    (job / "raw").mkdir(parents=True)
    (job / "raw" / "transcript.raw.json").write_text(
        json.dumps({"segments": []}), encoding="utf-8"
    )
    with pytest.raises(PreReviewError, match="no segments"):
        build_pre_review_package(job)
