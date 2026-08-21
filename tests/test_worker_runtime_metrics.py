from __future__ import annotations

from pathlib import Path

from vid_pipeline.models import TranscriptDocument, TranscriptSegment
from vid_pipeline.server.repository import Repository
from vid_pipeline.server.storage import LocalArtifactStore
from vid_pipeline.server.worker import process_job


class Processor:
    def process(self, media: Path, job: dict, work: Path) -> TranscriptDocument:
        assert media.is_file()
        (work / "audio.wav").write_bytes(b"wav")
        (work / "audio-quality.json").write_text('{"duration_seconds": 5.25}', encoding="utf-8")
        return TranscriptDocument(
            job_id=job["job_id"], language="fa",
            segments=[TranscriptSegment(1, 0.0, 4.5, "سلام دنیا", confidence=0.98)],
        )


def test_worker_publishes_timing_and_stage_history(tmp_path: Path) -> None:
    repo = Repository(f"sqlite:///{tmp_path / 'db.sqlite'}")
    job = {
        "job_id": "job-1",
        "status": "queued",
        "current_stage": "queued",
        "progress_percent": 0,
        "created_at": "2026-08-21T00:00:00+00:00",
        "started_at": None,
        "completed_at": None,
        "file_name": "input.mp3",
        "source": {"type": "upload", "upload_id": "up"},
    }
    repo.put_job(job)
    storage = LocalArtifactStore(tmp_path / "storage")
    media = storage.path("objects/input.mp3")
    media.parent.mkdir(parents=True, exist_ok=True)
    media.write_bytes(b"media")
    import hashlib
    repo.put_upload({
        "upload_id": "up", "status": "uploaded", "file_name": "input.mp3",
        "file_size": 5, "sha256": hashlib.sha256(b"media").hexdigest(),
        "object_key": "objects/input.mp3",
    })

    result = process_job("job-1", repo, storage, Processor())

    assert result["status"] == "completed"
    assert result["progress_percent"] == 100
    assert result["input_duration_seconds"] == 5.25
    assert result["output_duration_seconds"] == 4.5
    assert result["transcript_word_count"] == 2
    assert result["transcript_character_count"] == len("سلام دنیا")
    assert result["execution_seconds"] >= 0
    stages = [item["stage"] for item in result["stage_history"]]
    assert stages == [
        "queued", "materializing_source", "canonical_core", "quality_check", "rendering", "completed"
    ]
    assert "delivery/transcript.txt" in result["artifacts"]
