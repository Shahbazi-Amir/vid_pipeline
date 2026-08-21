from __future__ import annotations

from datetime import UTC, datetime

import pytest

from vid_pipeline.web_utils import (
    downloadable_artifacts,
    format_duration,
    job_timing,
    parse_release_lines,
    parse_url_lines,
    preferred_text_artifact,
    source_label,
    stage_rows,
)


def test_job_timing_reports_queue_execution_and_total() -> None:
    job = {
        "created_at": "2026-08-21T00:00:00+00:00",
        "started_at": "2026-08-21T00:00:10+00:00",
        "completed_at": "2026-08-21T00:01:10+00:00",
    }
    assert job_timing(job) == {
        "queue_wait_seconds": 10.0,
        "execution_seconds": 60.0,
        "total_seconds": 70.0,
    }


def test_running_job_uses_current_time() -> None:
    job = {
        "created_at": "2026-08-21T00:00:00+00:00",
        "started_at": "2026-08-21T00:00:05+00:00",
    }
    timing = job_timing(job, now=datetime(2026, 8, 21, 0, 0, 35, tzinfo=UTC))
    assert timing["queue_wait_seconds"] == 5.0
    assert timing["execution_seconds"] == 30.0
    assert timing["total_seconds"] == 35.0


def test_duration_formatting() -> None:
    assert format_duration(0) == "00:00"
    assert format_duration(65) == "01:05"
    assert format_duration(3661) == "1:01:01"
    assert format_duration(None) == "—"


def test_parse_multiple_urls_and_release_rows() -> None:
    assert parse_url_lines("https://a.example/x.mp3\n\nhttps://b.example/y.mp4") == [
        "https://a.example/x.mp3",
        "https://b.example/y.mp4",
    ]
    assert parse_release_lines("owner/repo | v1 | audio.mp3\nowner/repo | v2 | video.mp4") == [
        {"repository": "owner/repo", "tag": "v1", "asset": "audio.mp3"},
        {"repository": "owner/repo", "tag": "v2", "asset": "video.mp4"},
    ]


def test_invalid_release_row_is_rejected() -> None:
    with pytest.raises(ValueError, match="owner/repo"):
        parse_release_lines("broken | v1 | a.mp3")
    with pytest.raises(ValueError, match="نام فایل"):
        parse_release_lines("owner/repo | v1 | path/a.mp3")


def test_artifact_selection_prefers_delivery_then_machine() -> None:
    completed = ["delivery/transcript.md", "delivery/transcript.txt"]
    assert preferred_text_artifact(completed, "completed") == "delivery/transcript.txt"
    review = ["raw/transcript.raw.md", "machine/transcript.machine.txt"]
    assert preferred_text_artifact(review, "review_required") == "machine/transcript.machine.txt"
    assert downloadable_artifacts(review + ["audio/audio.wav"]) == review


def test_source_and_stage_rows_are_human_readable() -> None:
    job = {
        "status": "processing",
        "current_stage": "transcribe_primary",
        "source": {"type": "github_release", "repository": "o/r", "tag": "v1", "asset": "a.mp3"},
        "stage_history": [
            {"stage": "queued", "at": "t0", "progress_percent": 0},
            {"stage": "materializing_source", "at": "t1", "progress_percent": 5},
            {"stage": "normalize_audio", "at": "t2", "progress_percent": 25},
            {"stage": "transcribe_primary", "at": "t3", "progress_percent": 35},
        ],
    }
    assert source_label(job) == "o/r@v1 / a.mp3"
    rows = {row["stage"]: row for row in stage_rows(job)}
    assert rows["normalize_audio"]["state"] == "done"
    assert rows["transcribe_primary"]["state"] == "active"
    assert rows["rendering"]["state"] == "pending"
