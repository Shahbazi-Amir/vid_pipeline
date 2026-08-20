"""FastAPI control plane for resumable uploads, jobs and artifacts."""

from __future__ import annotations

import hashlib
import mimetypes
import os
import re
import secrets
from pathlib import Path
from typing import Any

from fastapi import Depends, FastAPI, Header, HTTPException, Request
from fastapi.responses import FileResponse

from vid_pipeline.online_client import MEDIA_EXTENSIONS
from vid_pipeline.profiles import DEFAULT_PROFILE, resolve_transcription_model
from vid_pipeline.server.queue import InlineJobQueue, JobQueue, RedisJobQueue
from vid_pipeline.server.repository import Repository, now
from vid_pipeline.server.storage import LocalArtifactStore

SAFE_NAME = re.compile(r"[^A-Za-z0-9._-]+")


def create_app(
    *,
    repository: Repository | None = None,
    storage: LocalArtifactStore | None = None,
    queue: JobQueue | None = None,
    token: str | None = None,
    max_file_size: int | None = None,
) -> FastAPI:
    root = Path(os.getenv("VID_PIPELINE_STORAGE_ROOT", "./.vid_pipeline/server")).resolve()
    root.mkdir(parents=True, exist_ok=True)
    repository = repository or Repository(
        os.getenv("VID_PIPELINE_DATABASE_URL", f"sqlite:///{root / 'pipeline.db'}")
    )
    storage = storage or LocalArtifactStore(root)
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
        return {"status": "ok"}

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
            "upload_id": upload_id, "file_name": safe, "file_size": size, "sha256": digest,
            "content_type": str(payload.get("content_type", "")), "uploaded_bytes": 0,
            "status": "uploading", "object_key": "", "created_at": now(), "updated_at": now(),
        }
        repository.put_upload(value)
        storage.path(f"uploads/{upload_id}/parts").mkdir(parents=True, exist_ok=True)
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
        target = storage.path(f"uploads/{upload_id}/parts/{part_number:08d}.part")
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
        return {"part_number": part_number, "size": written, "uploaded_bytes": value["uploaded_bytes"]}

    @app.post("/v1/uploads/{upload_id}/complete", dependencies=auth)
    def complete_upload(upload_id: str) -> dict[str, Any]:
        value = repository.upload(upload_id)
        if not value:
            raise HTTPException(404, "upload not found")
        target = storage.path(f"objects/{value['sha256']}/{value['file_name']}")
        target.parent.mkdir(parents=True, exist_ok=True)
        digest = hashlib.sha256()
        total = 0
        with target.open("wb") as output:
            for part in sorted(storage.path(f"uploads/{upload_id}/parts").glob("*.part")):
                with part.open("rb") as source:
                    while chunk := source.read(1024 * 1024):
                        digest.update(chunk)
                        output.write(chunk)
                        total += len(chunk)
        if total != value["file_size"] or digest.hexdigest() != value["sha256"]:
            target.unlink(missing_ok=True)
            raise HTTPException(422, "size or hash mismatch")
        guessed = mimetypes.guess_type(value["file_name"])[0] or ""
        if guessed and not (guessed.startswith("audio/") or guessed.startswith("video/")):
            target.unlink(missing_ok=True)
            raise HTTPException(415, "invalid MIME type")
        value.update(status="uploaded", uploaded_bytes=total,
                     object_key=str(target.relative_to(storage.root)), updated_at=now())
        repository.put_upload(value)
        return value

    @app.post("/v1/jobs", dependencies=auth)
    def create_job(payload: dict[str, Any]) -> dict[str, Any]:
        upload = repository.upload(str(payload.get("upload_id", "")))
        if not upload or upload["status"] != "uploaded":
            raise HTTPException(409, "upload is not complete")

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
            "job_id": job_id, "upload_id": upload["upload_id"],
            "input_object": upload["object_key"], "input_hash": upload["sha256"],
            "file_name": upload["file_name"], "file_size": upload["file_size"],
            "profile": profile, "model": model,
            "language": payload.get("language", "fa"),
            "audio_profile": payload.get("audio_profile", "safe"),
            "review_settings": {"editorial": bool(payload.get("editorial", True))},
            "status": "queued", "progress_percent": 0, "current_stage": "queued",
            "created_at": now(), "started_at": None, "completed_at": None, "retries": 0,
            "error": None, "artifacts": [],
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
        value = get_job(job_id)
        queue.cancel(job_id)
        value.update(status="cancelled", current_stage="cancelled", completed_at=now())
        repository.put_job(value)
        return value

    @app.post("/v1/jobs/{job_id}/retry", dependencies=auth)
    def retry_job(job_id: str) -> dict[str, Any]:
        value = get_job(job_id)
        value.update(status="queued", current_stage="queued", error=None,
                     retries=int(value["retries"]) + 1)
        repository.put_job(value)
        queue.enqueue(job_id)
        return value

    @app.get("/v1/jobs/{job_id}/artifacts", dependencies=auth)
    def list_artifacts(job_id: str) -> dict[str, Any]:
        value = get_job(job_id)
        return {"artifacts": [
            {"name": name, "size": storage.path(f"jobs/{job_id}/{name}").stat().st_size}
            for name in value.get("artifacts", [])
        ]}

    @app.get("/v1/jobs/{job_id}/artifacts/{artifact_name:path}", dependencies=auth)
    def download_artifact(job_id: str, artifact_name: str) -> FileResponse:
        value = get_job(job_id)
        if artifact_name not in value.get("artifacts", []):
            raise HTTPException(404, "artifact not found")
        path = storage.path(f"jobs/{job_id}/{artifact_name}")
        return FileResponse(path, filename=path.name)

    return app


app = create_app()
