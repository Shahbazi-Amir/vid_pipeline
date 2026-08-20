"""Background worker orchestration. Heavy dependencies are imported only inside processing."""

from __future__ import annotations

import json
import os
import shutil
from pathlib import Path
from typing import Any, Protocol

from vid_pipeline.models import TranscriptDocument, TranscriptSegment
from vid_pipeline.profiles import DEFAULT_PROFILE, resolve_transcription_model
from vid_pipeline.render import render_outputs
from vid_pipeline.server.quality_gate import evaluate_transcript_quality
from vid_pipeline.server.repository import Repository, now
from vid_pipeline.server.storage import LocalArtifactStore


class Processor(Protocol):
    def process(self, media: Path, job: dict[str, Any], work: Path) -> TranscriptDocument: ...


class WhisperProcessor:
    def process(self, media: Path, job: dict[str, Any], work: Path) -> TranscriptDocument:
        from vid_pipeline.audio import normalize_audio
        from vid_pipeline.transcribe import TranscriptionConfig, transcribe_audio

        model = resolve_transcription_model(
            str(job.get("profile", DEFAULT_PROFILE)),
            str(job.get("model", "")),
            allow_local_path=True,
        )
        job["model"] = model

        audio = normalize_audio(
            media, work / "audio.wav", overwrite=True,
            profile=job.get("audio_profile", "safe"),
        )
        raw_json = work / "transcript.raw.json"
        raw_md = work / "transcript.raw.md"
        result = transcribe_audio(
            audio, raw_json, raw_md,
            TranscriptionConfig(model=model, language=job["language"]),
        )
        segments = [
            TranscriptSegment(
                segment_id=index,
                start=float(item["start"]),
                end=float(item["end"]),
                text=str(item["text"]).strip(),
                confidence=(
                    sum(float(word.get("probability", 0.0)) for word in item.get("words") or [])
                    / len(item.get("words") or [])
                    if item.get("words")
                    else None
                ),
                suspicious_flags=list(item.get("review_flags") or []),
            )
            for index, item in enumerate(result.get("segments", []), 1)
        ]
        return TranscriptDocument(job_id=job["job_id"], language=job["language"], segments=segments)


def _write_terminal_state(
    job: dict[str, Any], storage: LocalArtifactStore, artifacts: list[str]
) -> None:
    root = storage.path(f"jobs/{job['job_id']}")
    (root / "state.json").write_text(json.dumps(job, indent=2) + "\n")
    (root / "manifest.json").write_text(
        json.dumps({"job_id": job["job_id"], "status": job["status"], "artifacts": artifacts}, indent=2)
        + "\n"
    )


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

        processor_raw = work / "transcript.raw.json"
        if processor_raw.is_file():
            try:
                raw_payload = json.loads(processor_raw.read_text(encoding="utf-8"))
            except json.JSONDecodeError as exc:
                raise ValueError("processor produced invalid raw transcript JSON") from exc
        else:
            raw_payload = document.to_dict()

        raw = storage.path(f"jobs/{job_id}/raw/transcript.raw.json")
        raw.parent.mkdir(parents=True, exist_ok=True)
        raw.write_text(json.dumps(raw_payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        raw_md = raw.parent / "transcript.raw.md"
        processor_raw_md = work / "transcript.raw.md"
        if processor_raw_md.is_file():
            shutil.copyfile(processor_raw_md, raw_md)
        else:
            raw_md.write_text(document.text + "\n", encoding="utf-8")

        machine = storage.path(f"jobs/{job_id}/machine")
        machine.mkdir(parents=True, exist_ok=True)
        (machine / "transcript.machine.json").write_text(
            json.dumps(document.to_dict(), ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
        (machine / "transcript.machine.md").write_text(document.text + "\n", encoding="utf-8")
        (machine / "transcript.machine.txt").write_text(document.text + "\n", encoding="utf-8")

        job.update(status="quality_check", current_stage="quality_check", progress_percent=80)
        repository.put_job(job)
        quality_report = evaluate_transcript_quality(document, raw_payload)
        quality_dir = storage.path(f"jobs/{job_id}/quality")
        quality_dir.mkdir(parents=True, exist_ok=True)
        quality = quality_dir / "quality-report.json"
        quality.write_text(
            json.dumps(quality_report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )

        final_dir = storage.path(f"jobs/{job_id}/final")
        delivery = storage.path(f"jobs/{job_id}/delivery")
        if not quality_report["valid"]:
            shutil.rmtree(final_dir, ignore_errors=True)
            shutil.rmtree(delivery, ignore_errors=True)
            result = storage.path(f"jobs/{job_id}/result.json")
            result.write_text(
                json.dumps(
                    {
                        "job_id": job_id,
                        "status": "review_required",
                        "quality_gate": {
                            "decision": quality_report["decision"],
                            "overall_score": quality_report["overall_score"],
                            "reasons": quality_report["gate_reasons"],
                        },
                    },
                    ensure_ascii=False,
                    indent=2,
                )
                + "\n",
                encoding="utf-8",
            )
            artifacts = [
                "raw/transcript.raw.json",
                "raw/transcript.raw.md",
                "machine/transcript.machine.json",
                "machine/transcript.machine.md",
                "machine/transcript.machine.txt",
                "quality/quality-report.json",
                "result.json",
            ]
            job.update(
                status="review_required",
                current_stage="quality_gate",
                progress_percent=90,
                completed_at=now(),
                artifacts=artifacts,
                error=None,
                quality_gate={
                    "decision": quality_report["decision"],
                    "overall_score": quality_report["overall_score"],
                    "reasons": quality_report["gate_reasons"],
                },
            )
            repository.put_job(job)
            _write_terminal_state(job, storage, artifacts)
            shutil.rmtree(work, ignore_errors=True)
            return job

        job.update(status="rendering", current_stage="rendering", progress_percent=90)
        repository.put_job(job)
        shutil.rmtree(final_dir, ignore_errors=True)
        shutil.rmtree(delivery, ignore_errors=True)
        outputs = render_outputs(document, final_dir)
        (final_dir / "quality-report.json").write_text(
            json.dumps(quality_report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
        (final_dir / "result.json").write_text(
            json.dumps(
                {
                    "job_id": job_id,
                    "status": "completed",
                    "quality_gate": {
                        "decision": "pass",
                        "overall_score": quality_report["overall_score"],
                        "reasons": [],
                    },
                },
                ensure_ascii=False,
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )
        delivery.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(outputs["markdown"], delivery / "transcript.md")
        shutil.copyfile(outputs["text"], delivery / "transcript.txt")
        shutil.copyfile(outputs["timecoded_markdown"], delivery / "transcript.timestamped.md")
        artifacts = [
            str(path.relative_to(storage.path(f"jobs/{job_id}")))
            for path in sorted(delivery.iterdir())
        ]
        job.update(
            status="completed", current_stage="completed", progress_percent=100,
            completed_at=now(), artifacts=artifacts, error=None,
            quality_gate={
                "decision": "pass",
                "overall_score": quality_report["overall_score"],
                "reasons": [],
            },
        )
        repository.put_job(job)
        _write_terminal_state(job, storage, artifacts)
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
