"""Background worker orchestration. Queue/state logic lives here; media logic does not."""

from __future__ import annotations

import json
import os
import shutil
import time
from pathlib import Path
from typing import Any, Protocol

from vid_pipeline.models import TranscriptDocument
from vid_pipeline.render import render_outputs
from vid_pipeline.server.processing import StageCallback, process_media_core
from vid_pipeline.server.quality_gate import evaluate_transcript_quality
from vid_pipeline.server.repository import ConcurrentUpdateError, Repository, now
from vid_pipeline.server.sources import SourceMaterializer
from vid_pipeline.server.storage import (
    LocalArtifactStore,
    ObjectStore,
    object_store_from_env,
)


class Processor(Protocol):
    """Test seam for deterministic worker tests."""

    def process(self, media: Path, job: dict[str, Any], work: Path) -> TranscriptDocument: ...


def _copy_if_present(source: Path, destination: Path) -> bool:
    if not source.is_file():
        return False
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(source, destination)
    return True


def _ensure_stage_history(job: dict[str, Any]) -> list[dict[str, Any]]:
    history = job.get("stage_history")
    if not isinstance(history, list):
        history = []
        job["stage_history"] = history
    if not history:
        history.append(
            {
                "stage": "queued",
                "status": "queued",
                "progress_percent": 0,
                "at": job.get("created_at") or now(),
            }
        )
    return history


def _advance_job(
    job: dict[str, Any],
    repository: Repository,
    *,
    status: str,
    stage: str,
    progress: int,
    **updates: Any,
) -> None:
    history = _ensure_stage_history(job)
    if not history or history[-1].get("stage") != stage:
        history.append(
            {
                "stage": stage,
                "status": status,
                "progress_percent": progress,
                "at": now(),
            }
        )
    job.update(
        status=status,
        current_stage=stage,
        progress_percent=progress,
        **updates,
    )
    repository.put_job(job)


def _copy_runtime_metrics(
    job: dict[str, Any],
    work: Path,
    document: TranscriptDocument,
    raw_payload: dict[str, Any],
    stage_timings: dict[str, float],
) -> None:
    input_duration = raw_payload.get("duration")
    if input_duration is None:
        audio_quality = work / "audio-quality.json"
        if audio_quality.is_file():
            try:
                input_duration = json.loads(audio_quality.read_text(encoding="utf-8")).get(
                    "duration_seconds"
                )
            except (OSError, json.JSONDecodeError):
                input_duration = None
    output_duration = max((float(segment.end) for segment in document.segments), default=0.0)
    if input_duration is not None:
        job["input_duration_seconds"] = round(float(input_duration), 3)
    job["output_duration_seconds"] = round(output_duration, 3)
    job["transcript_character_count"] = len(document.text)
    job["transcript_word_count"] = len(document.text.split())
    job["stage_timings"] = dict(stage_timings)


def _write_terminal_state(
    job: dict[str, Any], storage: LocalArtifactStore, artifacts: list[str]
) -> None:
    root = storage.path(f"jobs/{job['job_id']}")
    (root / "state.json").write_text(json.dumps(job, indent=2) + "\n")
    (root / "manifest.json").write_text(
        json.dumps(
            {"job_id": job["job_id"], "status": job["status"], "artifacts": artifacts},
            indent=2,
        )
        + "\n"
    )


def _sync_artifacts(
    job_id: str,
    job_root: Path,
    artifacts: list[str],
    object_store: ObjectStore,
) -> None:
    """Publish only declared artifacts after they exist locally."""
    for name in artifacts:
        source = (job_root / name).resolve()
        if job_root.resolve() not in source.parents:
            raise ValueError(f"unsafe artifact path: {name}")
        if not source.is_file():
            raise FileNotFoundError(f"declared artifact is missing: {name}")
        object_store.put_file(source, f"jobs/{job_id}/{name}")


def _run_processing_core(
    media: Path,
    job: dict[str, Any],
    work: Path,
    processor: Processor | None,
    *,
    stage_callback: StageCallback | None = None,
) -> tuple[TranscriptDocument, dict[str, Any], dict[str, Any], dict[str, float]]:
    if processor is None:
        core = process_media_core(media, job, work, stage_callback=stage_callback)
        return core.document, core.raw_payload, core.quality_report, core.timings

    document = processor.process(media, job, work)
    processor_raw = work / "transcript.raw.json"
    if processor_raw.is_file():
        try:
            raw_payload = json.loads(processor_raw.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise ValueError("processor produced invalid raw transcript JSON") from exc
    else:
        raw_payload = document.to_dict()
    return document, raw_payload, evaluate_transcript_quality(document, raw_payload), {}


def _latest_after_concurrency(repository: Repository, job_id: str) -> dict[str, Any]:
    latest = repository.job(job_id)
    if latest is None:
        raise ConcurrentUpdateError(f"job disappeared during concurrent update: {job_id}")
    return latest


def process_job(
    job_id: str,
    repository: Repository,
    storage: LocalArtifactStore,
    processor: Processor | None = None,
    *,
    object_store: ObjectStore | None = None,
) -> dict[str, Any]:
    object_store = object_store or storage
    job = repository.job(job_id)
    if not job:
        raise ValueError(f"unknown job: {job_id}")
    work = storage.path(f"jobs/{job_id}/work")
    work.mkdir(parents=True, exist_ok=True)
    execution_started = time.monotonic()
    try:
        _advance_job(
            job,
            repository,
            status="preparing",
            stage="materializing_source",
            progress=5,
            started_at=job.get("started_at") or now(),
        )
        media = SourceMaterializer(repository, object_store).materialize(job, work)
        job["file_name"] = job.get("file_name") or media.name
        job["file_size"] = int(job.get("file_size") or media.stat().st_size)
        repository.put_job(job)

        _advance_job(
            job,
            repository,
            status="processing",
            stage="canonical_core",
            progress=20,
        )

        def core_stage(stage: str, progress: int) -> None:
            _advance_job(
                job,
                repository,
                status="processing",
                stage=stage,
                progress=progress,
            )

        document, raw_payload, quality_report, stage_timings = _run_processing_core(
            media,
            job,
            work,
            processor,
            stage_callback=core_stage if processor is None else None,
        )

        latest = repository.job(job_id)
        if latest and int(latest.get("_revision", 0)) != int(job.get("_revision", 0)):
            return latest

        _copy_runtime_metrics(job, work, document, raw_payload, stage_timings)
        repository.put_job(job)

        job_root = storage.path(f"jobs/{job_id}")
        source_info = job_root / "source-materialization.json"
        source_info.write_text(
            json.dumps(job.get("source_materialization") or {}, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )

        raw_root = job_root / "raw"
        raw_root.mkdir(parents=True, exist_ok=True)
        raw_json = raw_root / "transcript.raw.json"
        raw_json.write_text(
            json.dumps(raw_payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
        raw_md = raw_root / "transcript.raw.md"
        if not _copy_if_present(work / "transcript.raw.md", raw_md):
            raw_md.write_text(document.text + "\n", encoding="utf-8")

        machine = job_root / "machine"
        machine.mkdir(parents=True, exist_ok=True)
        (machine / "transcript.machine.json").write_text(
            json.dumps(document.to_dict(), ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
        if not _copy_if_present(work / "transcript.machine.md", machine / "transcript.machine.md"):
            (machine / "transcript.machine.md").write_text(document.text + "\n", encoding="utf-8")
        if not _copy_if_present(work / "transcript.machine.txt", machine / "transcript.machine.txt"):
            (machine / "transcript.machine.txt").write_text(document.text + "\n", encoding="utf-8")

        audio_dir = job_root / "audio"
        _copy_if_present(work / "audio.wav", audio_dir / "audio-16k-mono.wav")
        _copy_if_present(work / "audio-quality.json", audio_dir / "audio-quality.json")

        diagnostics = job_root / "diagnostics"
        diagnostics.mkdir(parents=True, exist_ok=True)
        _copy_if_present(
            work / "targeted-retry-report.json",
            diagnostics / "targeted-retry-report.json",
        )
        _copy_if_present(work / "core-manifest.json", diagnostics / "core-manifest.json")

        _advance_job(
            job,
            repository,
            status="quality_check",
            stage="quality_check",
            progress=80,
        )
        quality_dir = job_root / "quality"
        quality_dir.mkdir(parents=True, exist_ok=True)
        quality = quality_dir / "quality-report.json"
        quality.write_text(
            json.dumps(quality_report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )

        final_dir = job_root / "final"
        delivery = job_root / "delivery"
        if not quality_report["valid"]:
            shutil.rmtree(final_dir, ignore_errors=True)
            shutil.rmtree(delivery, ignore_errors=True)
            result = job_root / "result.json"
            result.write_text(
                json.dumps(
                    {
                        "job_id": job_id,
                        "status": "review_required",
                        "review_status": "human_review_required",
                        "human_audio_verification": False,
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
                "source-materialization.json",
                "audio/audio-16k-mono.wav",
                "audio/audio-quality.json",
                "raw/transcript.raw.json",
                "raw/transcript.raw.md",
                "machine/transcript.machine.json",
                "machine/transcript.machine.md",
                "machine/transcript.machine.txt",
                "quality/quality-report.json",
                "result.json",
            ]
            for name in (
                "diagnostics/targeted-retry-report.json",
                "diagnostics/core-manifest.json",
            ):
                if (job_root / name).is_file():
                    artifacts.append(name)
            _sync_artifacts(job_id, job_root, artifacts, object_store)
            _advance_job(
                job,
                repository,
                status="review_required",
                stage="review_required",
                progress=100,
                completed_at=now(),
                artifacts=artifacts,
                error=None,
                execution_seconds=round(time.monotonic() - execution_started, 6),
                quality_gate={
                    "decision": quality_report["decision"],
                    "overall_score": quality_report["overall_score"],
                    "reasons": quality_report["gate_reasons"],
                },
            )
            _write_terminal_state(job, storage, artifacts)
            shutil.rmtree(work, ignore_errors=True)
            return job

        _advance_job(
            job,
            repository,
            status="rendering",
            stage="rendering",
            progress=90,
        )
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
                    "review_status": "machine_quality_passed",
                    "human_audio_verification": False,
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
            str(path.relative_to(job_root))
            for path in sorted(delivery.iterdir())
        ]
        _sync_artifacts(job_id, job_root, artifacts, object_store)
        _advance_job(
            job,
            repository,
            status="completed",
            stage="completed",
            progress=100,
            completed_at=now(),
            artifacts=artifacts,
            error=None,
            execution_seconds=round(time.monotonic() - execution_started, 6),
            review_status="machine_quality_passed",
            human_audio_verification=False,
            quality_gate={
                "decision": "pass",
                "overall_score": quality_report["overall_score"],
                "reasons": [],
            },
        )
        _write_terminal_state(job, storage, artifacts)
        shutil.rmtree(work, ignore_errors=True)
        return job
    except ConcurrentUpdateError:
        return _latest_after_concurrency(repository, job_id)
    except Exception as exc:
        latest = repository.job(job_id)
        if latest and latest.get("status") == "cancelled":
            return latest
        failure = latest or job
        try:
            _advance_job(
                failure,
                repository,
                status="failed",
                stage="failed",
                progress=100,
                error=f"{type(exc).__name__}: {exc}",
                completed_at=now(),
                execution_seconds=round(time.monotonic() - execution_started, 6),
            )
        except ConcurrentUpdateError:
            return _latest_after_concurrency(repository, job_id)
        raise


def run_job_from_environment(job_id: str) -> dict[str, Any]:
    root = Path(os.getenv("VID_PIPELINE_STORAGE_ROOT", "/data/storage"))
    database = os.getenv("VID_PIPELINE_DATABASE_URL", f"sqlite:///{root / 'pipeline.db'}")
    workspace = LocalArtifactStore(root)
    return process_job(
        job_id,
        Repository(database),
        workspace,
        object_store=object_store_from_env(root),
    )
