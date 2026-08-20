"""FastAPI control plane for resumable uploads, jobs and artifacts."""

from __future__ import annotations

import hashlib
import mimetypes
import os
import re
import secrets
from pathlib import Path
from typing import Any, Iterator

from fastapi import Depends, FastAPI, Header, HTTPException, Request
from fastapi.responses import FileResponse, StreamingResponse

from vid_pipeline.online_client import MEDIA_EXTENSIONS
from vid_pipeline.profiles import DEFAULT_PROFILE, resolve_transcription_model
from vid_pipeline.server.queue import InlineJobQueue, JobQueue, RedisJobQueue
from vid_pipeline.server.repository import ConcurrentUpdateError, Repository, now
from vid_pipeline.server.sources import normalize_source_request
from vid_pipeline.server.storage import (
    LocalArtifactStore,
    ObjectStore,
    object_store_from_env,
)

SAFE_NAME = re.compile(r"[^A-Za-z0-9._-]+")
ACTIVE_JOB_STATUSES = {"queued", "preparing", "processing", "quality_check", "rendering"}
RETRYABLE_JOB_STATUSES = {"failed", "review_required", "cancelled"}


def _stream_object(store: ObjectStore, key: str) -> Iterator[bytes]:
    body = store.open(key)
    try:
        while chunk := body.read(1024 * 1024):
            yield chunk
    finally:
        body.close()


def create_app(
    *,
    repository: Repository | None = None,
    storage: LocalArtifactStore | None = None,
    object_store: ObjectStore | None = None,
    queue: JobQueue | None = None,
    token: str | None = None,
    max_file_size: int | None = None,
) -> FastAPI:
    root = Path(os.getenv("VID_PIPELINE_STORAGE_ROOT", "./.vid_pipeline/server")).resolve()
    root.mkdir(parents=True, exist_ok=True)
    repository = repository or Repository(
        os.getenv("VID_PIPELINE_DATABASE_URL", f"sqlite:///{root / 'pipeline.db'}")
    )
    workspace = storage or LocalArtifactStore(root)
    object_store = object_store or (workspace if storage is not None else object_store_from_env(root))
    if queue is None:
        redis_url = os.getenv("VID_PIPELINE_REDIS_URL", "")
        queue = RedisJobQueue(redis_url) if redis_url else InlineJobQueue()
    expected_token = token if token is not None else os.getenv("VID_PIPELINE_API_TOKEN", "")
    limit = max_file_size or int(os.getenv("VID_PIPELINE_MAX_FILE_SIZE", str(50 * 1024**3)))
    app = FastAPI(title="Video Pipeline Control Plane", version="1")

    def authorize(authorization: str = Header("")) -> None:
        if expected_token and not secrets.compare_digest(
            authorization, f"Bearer {expected_token}"
        ):
            raise HTTPException(401, "invalid bearer token")

    auth = [Depends(authorize)]

    @app.get("/health")
    def health() -> dict[str, str]:
        return {
            "status": "ok",
            "storage_backend": "local" if isinstance(object_store, LocalArtifactStore) else "object",
        }

    @app.post("/v1/uploads", dependencies=auth)
    def create_upload(payload: dict[str, Any]) -> dict[str, Any]:
        name = Path(str(payload.get("file_name", ""))).name
        extension = Path(name).suffix.lower()
        size = int(payload.get("file_size", -1))
        digest = str(payload.get("sha256", "")).lower()
        if not name or extension not in MEDIA_EXTENSIONS:
            raise HTTPException(415, "invalid file type")
        if size < 0 or size > limit:
            raise HTTPException(413, "file is too large")
        if not re.fullmatch(r"[a-f0-9]{64}", digest):
            raise HTTPException(422, "invalid SHA-256")
        duplicate = repository.upload_by_hash(digest)
        if duplicate:
            return duplicate
        upload_id = secrets.token_hex(16)
        safe = SAFE_NAME.sub("-", name)
        value = {
            "upload_id": upload_id,
            "file_name": safe,
            "file_size": size,
            "sha256": digest,
            "content_type": str(payload.get("content_type", "")),
            "uploaded_bytes": 0,
            "status": "uploading",
            "object_key": "",
            "created_at": now(),
            "updated_at": now(),
        }
        repository.put_upload(value)
        workspace.path(f"uploads/{upload_id}/parts").mkdir(parents=True, exist_ok=True)
        return value

    @app.get("/v1/uploads/{upload_id}", dependencies=auth)
    def get_upload(upload_id: str) -> dict[str, Any]:
        value = repository.upload(upload_id)
        if not value:
            raise HTTPException(404, "upload not found")
        return value

    @app.put("/v1/uploads/{upload_id}/parts/{part_number}", dependencies=auth)
    async def upload_part(upload_id: str, part_number: int, request: Request) -> dict[str, Any]:
        value = repository.upload(upload_id)
        if not value:
            raise HTTPException(404, "upload not found")
        if part_number < 1:
            raise HTTPException(422, "invalid part number")
        target = workspace.path(f"uploads/{upload_id}/parts/{part_number:08d}.part")
        target.parent.mkdir(parents=True, exist_ok=True)
        written = 0
        with target.open("wb") as handle:
            async for chunk in request.stream():
                written += len(chunk)
                if value["uploaded_bytes"] + written > value["file_size"]:
                    target.unlink(missing_ok=True)
                    raise HTTPException(413, "upload exceeds declared size")
                handle.write(chunk)
        value["uploaded_bytes"] = sum(
            item.stat().st_size for item in target.parent.glob("*.part")
        )
        value["updated_at"] = now()
        repository.put_upload(value)
        return {
            "part_number": part_number,
            "size": written,
            "uploaded_bytes": value["uploaded_bytes"],
        }

    @app.post("/v1/uploads/{upload_id}/complete", dependencies=auth)
    def complete_upload(upload_id: str) -> dict[str, Any]:
        value = repository.upload(upload_id)
        if not value:
            raise HTTPException(404, "upload not found")
        staging = workspace.path(f"uploads/{upload_id}/assembled/{value['file_name']}")
        staging.parent.mkdir(parents=True, exist_ok=True)
        digest = hashlib.sha256()
        total = 0
        with staging.open("wb") as output:
            for part in sorted(workspace.path(f"uploads/{upload_id}/parts").glob("*.part")):
                with part.open("rb") as source:
                    while chunk := source.read(1024 * 1024):
                        digest.update(chunk)
                        output.write(chunk)
                        total += len(chunk)
        if total != value["file_size"] or digest.hexdigest() != value["sha256"]:
            staging.unlink(missing_ok=True)
            raise HTTPException(422, "size or hash mismatch")
        guessed = mimetypes.guess_type(value["file_name"])[0] or ""
        if guessed and not (guessed.startswith("audio/") or guessed.startswith("video/")):
            staging.unlink(missing_ok=True)
            raise HTTPException(415, "invalid MIME type")
        object_key = f"objects/{value['sha256']}/{value['file_name']}"
        object_store.put_file(staging, object_key)
        value.update(
            status="uploaded",
            uploaded_bytes=total,
            object_key=object_key,
            updated_at=now(),
        )
        repository.put_upload(value)
        return value

    @app.post("/v1/jobs", dependencies=auth)
    def create_job(payload: dict[str, Any]) -> dict[str, Any]:
        try:
            source = normalize_source_request(payload, repository)
        except ValueError as exc:
            message = str(exc)
            raise HTTPException(409 if "upload is not complete" in message else 422, message) from exc
        profile = str(payload.get("profile", DEFAULT_PROFILE) or DEFAULT_PROFILE)
        try:
            model = resolve_transcription_model(
                profile,
                str(payload.get("model", "") or ""),
                allow_local_path=False,
            )
        except ValueError as exc:
            raise HTTPException(422, str(exc)) from exc
        job_id = secrets.token_hex(12)
        value = {
            "job_id": job_id,
            "source": source,
            "upload_id": source.get("upload_id", ""),
            "input_object": source.get("object_key", ""),
            "input_hash": source.get("sha256", ""),
            "file_name": source.get("file_name", source.get("asset", "")),
            "file_size": source.get("file_size", 0),
            "profile": profile,
            "model": model,
            "language": payload.get("language", "fa"),
            "audio_profile": payload.get("audio_profile", "safe"),
            "review_settings": {"editorial": bool(payload.get("editorial", True))},
            "status": "queued",
            "progress_percent": 0,
            "current_stage": "queued",
            "created_at": now(),
            "started_at": None,
            "completed_at": None,
            "retries": 0,
            "error": None,
            "artifacts": [],
        }
        repository.put_job(value)
        queue.enqueue(job_id)
        return value

    @app.get("/v1/jobs", dependencies=auth)
    def list_jobs() -> dict[str, Any]:
        return {"jobs": repository.jobs()}

    @app.get("/v1/jobs/{job_id}", dependencies=auth)
    def get_job(job_id: str) -> dict[str, Any]:
        value = repository.job(job_id)
        if not value:
            raise HTTPException(404, "job not found")
        return value

    @app.post("/v1/jobs/{job_id}/cancel", dependencies=auth)
    def cancel_job(job_id: str) -> dict[str, Any]:
        if not repository.job(job_id):
            raise HTTPException(404, "job not found")
        try:
            value = repository.transition_job(
                job_id,
                expected_statuses=ACTIVE_JOB_STATUSES,
                updates={
                    "status": "cancelled",
                    "current_stage": "cancelled",
                    "completed_at": now(),
                    "error": None,
                },
            )
        except ConcurrentUpdateError as exc:
            raise HTTPException(409, str(exc)) from exc
        try:
            queue.cancel(job_id)
        except Exception as exc:
            # The DB transition remains authoritative; a worker holding a stale
            # revision cannot publish over this cancellation.
            value["queue_cancel_warning"] = f"{type(exc).__name__}: {exc}"
        return value

    @app.post("/v1/jobs/{job_id}/retry", dependencies=auth)
    def retry_job(job_id: str) -> dict[str, Any]:
        current = repository.job(job_id)
        if not current:
            raise HTTPException(404, "job not found")
        try:
            value = repository.transition_job(
                job_id,
                expected_statuses=RETRYABLE_JOB_STATUSES,
                updates={
                    "status": "queued",
                    "current_stage": "queued",
                    "error": None,
                    "completed_at": None,
                    "progress_percent": 0,
                    "retries": int(current.get("retries", 0)) + 1,
                },
            )
        except ConcurrentUpdateError as exc:
            raise HTTPException(409, str(exc)) from exc
        queue.enqueue(job_id)
        return value

    @app.get("/v1/jobs/{job_id}/artifacts", dependencies=auth)
    def list_artifacts(job_id: str) -> dict[str, Any]:
        value = get_job(job_id)
        artifacts = []
        for name in value.get("artifacts", []):
            key = f"jobs/{job_id}/{name}"
            try:
                size = object_store.size(key)
            except (FileNotFoundError, KeyError):
                continue
            artifacts.append({"name": name, "size": size})
        return {"artifacts": artifacts}

    @app.get("/v1/jobs/{job_id}/artifacts/{artifact_name:path}", dependencies=auth)
    def download_artifact(job_id: str, artifact_name: str):
        value = get_job(job_id)
        if artifact_name not in value.get("artifacts", []):
            raise HTTPException(404, "artifact not found")
        key = f"jobs/{job_id}/{artifact_name}"
        if isinstance(object_store, LocalArtifactStore):
            path = object_store.path(key)
            if not path.is_file():
                raise HTTPException(404, "artifact not found")
            return FileResponse(path, filename=path.name)
        try:
            size = object_store.size(key)
        except Exception as exc:
            raise HTTPException(404, "artifact not found") from exc
        return StreamingResponse(
            _stream_object(object_store, key),
            media_type="application/octet-stream",
            headers={
                "Content-Disposition": f'attachment; filename="{Path(artifact_name).name}"',
                "Content-Length": str(size),
            },
        )

    return app


app = create_app()
