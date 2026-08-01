"""Background worker orchestration. Heavy dependencies are imported only inside processing."""

from __future__ import annotations

import json
import os
import shutil
from pathlib import Path
from typing import Any, Protocol

from vid_pipeline.models import TranscriptDocument, TranscriptSegment
from vid_pipeline.render import render_outputs
from vid_pipeline.server.repository import Repository, now
from vid_pipeline.server.storage import LocalArtifactStore


class Processor(Protocol):
    def process(self, media: Path, job: dict[str, Any], work: Path) -> TranscriptDocument: ...


class WhisperProcessor:
    def process(self, media: Path, job: dict[str, Any], work: Path) -> TranscriptDocument:
        from vid_pipeline.audio import normalize_audio
        from vid_pipeline.transcribe import TranscriptionConfig, transcribe_audio

        audio = normalize_audio(
            media, work / "audio.wav", overwrite=True,
            profile=job.get("audio_profile", "safe"),
        )
        raw_json = work / "transcript.raw.json"
        raw_md = work / "transcript.raw.md"
        result = transcribe_audio(
            audio, raw_json, raw_md,
            TranscriptionConfig(model=job["model"], language=job["language"]),
        )
        segments = [
            TranscriptSegment(
                segment_id=index, start=float(item["start"]), end=float(item["end"]),
                text=str(item["text"]).strip(),
            )
            for index, item in enumerate(result.get("segments", []), 1)
        ]
        return TranscriptDocument(job_id=job["job_id"], language=job["language"], segments=segments)


def process_job(
    job_id: str,
    repository: Repository,
    storage: LocalArtifactStore,
    processor: Processor | None = None,
) -> dict[str, Any]:
    job = repository.job(job_id)
    if not job:
        raise ValueError(f"unknown job: {job_id}")
    work = storage.path(f"jobs/{job_id}/work")
    work.mkdir(parents=True, exist_ok=True)
    try:
        job.update(status="preparing", current_stage="preparing", progress_percent=5,
                   started_at=job.get("started_at") or now())
        repository.put_job(job)
        upload = repository.upload(job["upload_id"])
        if not upload or upload["status"] != "uploaded":
            raise ValueError("uploaded input is unavailable")
        media = storage.path(upload["object_key"])
        job.update(status="transcribing", current_stage="transcribing", progress_percent=30)
        repository.put_job(job)
        document = (processor or WhisperProcessor()).process(media, job, work)
        raw = storage.path(f"jobs/{job_id}/raw/transcript.raw.json")
        raw.parent.mkdir(parents=True, exist_ok=True)
        raw.write_text(json.dumps(document.to_dict(), ensure_ascii=False, indent=2) + "\n")
        (raw.parent / "transcript.raw.md").write_text(document.text + "\n")
        machine = storage.path(f"jobs/{job_id}/machine")
        machine.mkdir(parents=True, exist_ok=True)
        (machine / "transcript.machine.json").write_text(raw.read_text())
        (machine / "transcript.machine.md").write_text(document.text + "\n")
        (machine / "transcript.machine.txt").write_text(document.text + "\n")
        job.update(status="rendering", current_stage="rendering", progress_percent=85)
        repository.put_job(job)
        outputs = render_outputs(document, storage.path(f"jobs/{job_id}/final"))
        quality = storage.path(f"jobs/{job_id}/final/quality-report.json")
        quality.write_text(json.dumps({"segments": len(document.segments), "valid": True}) + "\n")
        result = storage.path(f"jobs/{job_id}/final/result.json")
        result.write_text(json.dumps({"job_id": job_id, "status": "completed"}) + "\n")
        state = storage.path(f"jobs/{job_id}/state.json")
        manifest = storage.path(f"jobs/{job_id}/manifest.json")
        artifacts = [
            str(Path(path).relative_to(storage.path(f"jobs/{job_id}")))
            for path in [*map(Path, outputs.values()), quality, result]
        ]
        job.update(
            status="completed", current_stage="completed", progress_percent=100,
            completed_at=now(), artifacts=artifacts, error=None,
        )
        repository.put_job(job)
        state.write_text(json.dumps(job, indent=2) + "\n")
        manifest.write_text(json.dumps({"job_id": job_id, "artifacts": artifacts}, indent=2) + "\n")
        shutil.rmtree(work, ignore_errors=True)
        return job
    except Exception as exc:
        job.update(status="failed", current_stage="failed", error=f"{type(exc).__name__}: {exc}",
                   completed_at=now())
        repository.put_job(job)
        raise


def run_job_from_environment(job_id: str) -> dict[str, Any]:
    root = Path(os.getenv("VID_PIPELINE_STORAGE_ROOT", "/data/storage"))
    database = os.getenv("VID_PIPELINE_DATABASE_URL", f"sqlite:///{root / 'pipeline.db'}")
    return process_job(job_id, Repository(database), LocalArtifactStore(root))
