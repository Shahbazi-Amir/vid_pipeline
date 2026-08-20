"""Lightweight resumable upload client. This module never imports worker code."""

from __future__ import annotations

import hashlib
import json
import os
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from vid_pipeline.profiles import DEFAULT_PROFILE, resolve_transcription_model

MEDIA_EXTENSIONS = {
    ".aac", ".ac3", ".aif", ".aiff", ".alac", ".amr", ".avi", ".caf",
    ".flac", ".m4a", ".m4v", ".mkv", ".mov", ".mp3", ".mp4", ".ogg",
    ".opus", ".wav", ".webm", ".wma",
}
CHUNK_SIZE = 8 * 1024 * 1024
TERMINAL_JOB_STATUSES = {
    "completed",
    "completed_with_fallback",
    "review_required",
    "failed",
    "cancelled",
}


def _now() -> str:
    return datetime.now(UTC).isoformat()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def discover(path: Path, recursive: bool = False) -> list[Path]:
    iterator = path.rglob("*") if recursive else path.glob("*")
    return sorted(
        item.resolve()
        for item in iterator
        if item.is_file() and item.suffix.lower() in MEDIA_EXTENSIONS
    )


@dataclass
class ClientRecord:
    local_path: str
    file_name: str
    file_size: int
    sha256: str
    upload_id: str = ""
    uploaded_bytes: int = 0
    remote_object_key: str = ""
    job_id: str = ""
    job_status: str = ""
    output_directory: str = ""
    last_error: str = ""
    retry_count: int = 0
    created_at: str = ""
    updated_at: str = ""


class ClientState:
    def __init__(self, root: Path = Path(".vid_pipeline")) -> None:
        self.root = root
        self.uploads = root / "uploads"
        self.jobs = root / "jobs"
        self.uploads.mkdir(parents=True, exist_ok=True)
        self.jobs.mkdir(parents=True, exist_ok=True)
        config = root / "client.json"
        if not config.exists():
            config.write_text('{"schema_version": 1}\n', encoding="utf-8")

    def _path(self, digest: str) -> Path:
        return self.uploads / f"{digest}.json"

    def load(self, digest: str) -> ClientRecord | None:
        path = self._path(digest)
        return ClientRecord(**json.loads(path.read_text(encoding="utf-8"))) if path.exists() else None

    def save(self, record: ClientRecord) -> None:
        record.updated_at = _now()
        path = self._path(record.sha256)
        temporary = path.with_suffix(".tmp")
        temporary.write_text(json.dumps(asdict(record), indent=2) + "\n", encoding="utf-8")
        temporary.replace(path)
        if record.job_id:
            (self.jobs / f"{record.job_id}.json").write_text(
                json.dumps(asdict(record), indent=2) + "\n", encoding="utf-8"
            )

    def records(self) -> list[ClientRecord]:
        return [ClientRecord(**json.loads(path.read_text())) for path in self.uploads.glob("*.json")]


class OnlineClient:
    def __init__(
        self,
        server_url: str,
        api_token: str = "",
        output_root: Path = Path("outputs"),
        state_root: Path = Path(".vid_pipeline"),
        *,
        timeout: float = 60.0,
        retries: int = 3,
        transport: Any = None,
    ) -> None:
        import httpx

        self.server_url = server_url.rstrip("/")
        self.output_root = output_root
        self.state = ClientState(state_root)
        self.retries = retries
        headers = {"Authorization": f"Bearer {api_token}"} if api_token else {}
        self.http = httpx.Client(
            base_url=self.server_url, headers=headers, timeout=timeout, transport=transport
        )

    def _request(self, method: str, url: str, **kwargs: Any) -> Any:
        error: Exception | None = None
        for attempt in range(self.retries + 1):
            try:
                response = self.http.request(method, url, **kwargs)
                response.raise_for_status()
                return response
            except Exception as exc:
                error = exc
                if attempt == self.retries:
                    raise
                time.sleep(min(2**attempt, 5))
        raise RuntimeError(str(error))

    def submit_file(
        self,
        path: Path,
        *,
        profile: str = DEFAULT_PROFILE,
        model: str = "",
        language: str = "fa",
        editorial: bool = True,
        resume: bool = True,
        force: bool = False,
        audio_profile: str = "safe",
    ) -> ClientRecord:
        path = path.resolve()
        if not path.is_file() or path.suffix.lower() not in MEDIA_EXTENSIONS:
            raise ValueError(f"unsupported media file: {path}")

        # Fail before hashing/uploading large media if the requested profile or
        # named model cannot be provisioned by the production worker.
        resolved_model = resolve_transcription_model(
            profile, model, allow_local_path=False
        )

        digest = sha256_file(path)
        record = self.state.load(digest) if resume and not force else None
        if record and record.job_id:
            return record
        record = record or ClientRecord(
            local_path=str(path), file_name=path.name, file_size=path.stat().st_size,
            sha256=digest, created_at=_now(),
        )
        try:
            if not record.upload_id:
                upload = self._request("POST", "/v1/uploads", json={
                    "file_name": path.name, "file_size": record.file_size,
                    "sha256": digest, "content_type": "application/octet-stream",
                }).json()
                record.upload_id = upload["upload_id"]
                record.uploaded_bytes = int(upload.get("uploaded_bytes", 0))
                record.remote_object_key = upload.get("object_key", "")
                self.state.save(record)
            remote = self._request("GET", f"/v1/uploads/{record.upload_id}").json()
            record.uploaded_bytes = int(remote.get("uploaded_bytes", record.uploaded_bytes))
            with path.open("rb") as handle:
                handle.seek(record.uploaded_bytes)
                part = record.uploaded_bytes // CHUNK_SIZE + 1
                while chunk := handle.read(CHUNK_SIZE):
                    self._request(
                        "PUT", f"/v1/uploads/{record.upload_id}/parts/{part}",
                        content=chunk, headers={"Content-Type": "application/octet-stream"},
                    )
                    record.uploaded_bytes += len(chunk)
                    self.state.save(record)
                    part += 1
            complete = self._request(
                "POST", f"/v1/uploads/{record.upload_id}/complete"
            ).json()
            record.remote_object_key = complete["object_key"]
            job = self._request("POST", "/v1/jobs", json={
                "upload_id": record.upload_id, "profile": profile, "model": resolved_model,
                "language": language, "editorial": editorial,
                "audio_profile": audio_profile,
            }).json()
            record.job_id = job["job_id"]
            record.job_status = job["status"]
            self.state.save(record)
            return record
        except Exception as exc:
            record.last_error = f"{type(exc).__name__}: {exc}"
            record.retry_count += 1
            self.state.save(record)
            raise

    def job_status(self, job_id: str) -> dict[str, Any]:
        return self._request("GET", f"/v1/jobs/{job_id}").json()

    def jobs(self) -> list[dict[str, Any]]:
        return self._request("GET", "/v1/jobs").json()["jobs"]

    def wait(self, job_id: str, interval: float = 2.0) -> dict[str, Any]:
        while True:
            job = self.job_status(job_id)
            if job["status"] in TERMINAL_JOB_STATUSES:
                return job
            time.sleep(interval)

    def download_results(self, job_id: str, *, resume: bool = True) -> Path:
        artifacts = self._request("GET", f"/v1/jobs/{job_id}/artifacts").json()["artifacts"]
        root = self.output_root / job_id
        for artifact in artifacts:
            relative = Path(artifact["name"])
            target = (root / relative).resolve()
            if root.resolve() not in target.parents:
                raise ValueError("unsafe artifact name")
            target.parent.mkdir(parents=True, exist_ok=True)
            offset = target.stat().st_size if resume and target.exists() else 0
            headers = {"Range": f"bytes={offset}-"} if offset else {}
            response = self._request(
                "GET", f"/v1/jobs/{job_id}/artifacts/{artifact['name']}", headers=headers
            )
            mode = "ab" if offset and response.status_code == 206 else "wb"
            with target.open(mode) as handle:
                for chunk in response.iter_bytes(1024 * 1024):
                    handle.write(chunk)
        return root

    def submit_folder(self, path: Path, *, upload_workers: int = 2, **kwargs: Any) -> list[ClientRecord]:
        files = discover(path, bool(kwargs.pop("recursive", False)))
        with ThreadPoolExecutor(max_workers=max(1, min(upload_workers, 8))) as pool:
            return list(pool.map(lambda item: self.submit_file(item, **kwargs), files))


def client_from_args(args: Any) -> OnlineClient:
    server = args.server_url or os.getenv("VID_PIPELINE_SERVER_URL", "")
    if not server:
        raise ValueError("--server-url or VID_PIPELINE_SERVER_URL is required")
    token = args.api_token or os.getenv("VID_PIPELINE_API_TOKEN", "")
    return OnlineClient(server, token, args.output_root)
