"""Lightweight GitHub Actions backend for local media.

This module deliberately depends only on the Python standard library and
``httpx``.  It never imports the local audio, ASR, or worker implementation.
"""

from __future__ import annotations

import hashlib
import json
import mimetypes
import os
import re
import subprocess
import tempfile
import time
import uuid
import zipfile
from collections.abc import Iterable
from dataclasses import asdict, dataclass
from datetime import UTC, datetime, timedelta
from email.utils import parsedate_to_datetime
from pathlib import Path
from typing import Any, BinaryIO

from vid_pipeline.online_client import MEDIA_EXTENSIONS

GITHUB_API = "https://api.github.com"
TEMPORARY_RELEASE_NAME = "vid-pipeline-temporary-inputs"
UPLOAD_WORKFLOW = "process-uploaded-video.yml"
URL_WORKFLOW = "process-video.yml"
MAX_ASSET_SIZE = 2 * 1024 * 1024 * 1024
CLOCK_SKEW_TOLERANCE = timedelta(minutes=10)
TERMINAL_CONCLUSIONS = {
    "success",
    "failure",
    "cancelled",
    "timed_out",
    "action_required",
    "stale",
}


def _now() -> str:
    return datetime.now(UTC).isoformat()


def _natural_key(path: Path) -> list[Any]:
    return [int(part) if part.isdigit() else part.casefold() for part in re.split(r"(\d+)", str(path))]


def discover_media(path: Path, recursive: bool = False) -> list[Path]:
    if not path.is_dir():
        raise ValueError(f"media folder does not exist: {path}")
    iterator = path.rglob("*") if recursive else path.glob("*")
    return sorted(
        (
            item.resolve()
            for item in iterator
            if item.is_file() and item.suffix.lower() in MEDIA_EXTENSIONS
        ),
        key=_natural_key,
    )


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def safe_asset_name(original_name: str, digest: str) -> str:
    name = Path(original_name).name
    stem = re.sub(r"[^A-Za-z0-9._-]+", "-", name).strip(".-") or "media"
    return f"vp-{digest[:16]}-{stem}"[:240]


def detect_repository() -> str:
    configured = os.getenv("VID_PIPELINE_GITHUB_REPO", "").strip()
    if configured:
        return configured
    try:
        remote = subprocess.run(
            ["git", "remote", "get-url", "origin"],
            check=True,
            capture_output=True,
            text=True,
            timeout=5,
        ).stdout.strip()
    except (OSError, subprocess.SubprocessError):
        return ""
    match = re.search(r"github\.com[/:]([^/]+/[^/]+?)(?:\.git)?$", remote)
    return match.group(1) if match else ""


@dataclass
class GitHubRequest:
    request_id: str
    local_path: str = ""
    original_name: str = ""
    safe_asset_name: str = ""
    file_size: int = 0
    sha256: str = ""
    release_id: int = 0
    asset_id: int = 0
    workflow_name: str = UPLOAD_WORKFLOW
    dispatch_id: str = ""
    dispatch_started_at: str = ""
    dispatch_server_at: str = ""
    workflow_run_id: int = 0
    workflow_run_url: str = ""
    artifact_id: int = 0
    artifact_name: str = ""
    job_id: str = ""
    status: str = "discovered"
    output_path: str = ""
    upload_started_at: str = ""
    upload_completed_at: str = ""
    workflow_started_at: str = ""
    workflow_completed_at: str = ""
    download_completed_at: str = ""
    remote_deleted_at: str = ""
    last_error: str = ""
    retry_count: int = 0


class GitHubState:
    def __init__(self, root: Path = Path(".vid_pipeline/github")) -> None:
        self.root = root
        root.mkdir(parents=True, exist_ok=True)

    def path(self, request_id: str) -> Path:
        if not re.fullmatch(r"[A-Za-z0-9_-]+", request_id):
            raise ValueError("invalid request id")
        return self.root / f"{request_id}.json"

    def save(self, request: GitHubRequest) -> None:
        target = self.path(request.request_id)
        temporary = target.with_suffix(f".{uuid.uuid4().hex}.tmp")
        temporary.write_text(
            json.dumps(asdict(request), ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        temporary.replace(target)

    def load(self, request_id: str) -> GitHubRequest:
        path = self.path(request_id)
        if not path.exists():
            raise ValueError(f"GitHub request does not exist: {request_id}")
        return GitHubRequest(**json.loads(path.read_text(encoding="utf-8")))

    def find_digest(self, digest: str, size: int) -> GitHubRequest | None:
        for path in sorted(self.root.glob("*.json")):
            try:
                request = GitHubRequest(**json.loads(path.read_text(encoding="utf-8")))
            except (OSError, TypeError, json.JSONDecodeError):
                continue
            if request.sha256 == digest and request.file_size == size:
                return request
        return None


class _ProgressFile:
    def __init__(self, handle: BinaryIO, size: int) -> None:
        self.handle = handle
        self.size = size
        self.sent = 0

    def read(self, amount: int = 64 * 1024) -> bytes:
        chunk = self.handle.read(amount)
        self.sent += len(chunk)
        return chunk

    def __iter__(self):
        while chunk := self.read():
            yield chunk

    def __len__(self) -> int:
        return self.size


class GitHubClient:
    def __init__(
        self,
        token: str,
        repository: str,
        *,
        ref: str = "main",
        output_root: Path = Path("outputs"),
        state_root: Path = Path(".vid_pipeline/github"),
        timeout: float = 60.0,
        retries: int = 2,
        transport: Any = None,
    ) -> None:
        if not token:
            raise ValueError("GitHub token is missing.")
        if not re.fullmatch(r"[^/\s]+/[^/\s]+", repository):
            raise ValueError("Repository could not be detected.")
        import httpx

        self.repository = repository
        self.ref = ref
        self.output_root = output_root
        self.state = GitHubState(state_root)
        self.retries = retries
        self.http = httpx.Client(
            base_url=GITHUB_API,
            headers={
                "Authorization": f"Bearer {token}",
                "Accept": "application/vnd.github+json",
                "X-GitHub-Api-Version": "2022-11-28",
                "User-Agent": "vid-pipeline-client",
            },
            timeout=timeout,
            transport=transport,
            follow_redirects=True,
        )
        self.public_http = httpx.Client(
            timeout=timeout,
            transport=transport,
            follow_redirects=True,
            headers={"User-Agent": "vid-pipeline-privacy-check"},
        )

    def close(self) -> None:
        self.http.close()
        self.public_http.close()

    def _request(self, method: str, url: str, **kwargs: Any) -> Any:
        last_error: Exception | None = None
        for attempt in range(self.retries + 1):
            try:
                response = self.http.request(method, url, **kwargs)
                response.raise_for_status()
                return response
            except Exception as exc:
                last_error = exc
                if attempt >= self.retries:
                    raise RuntimeError(f"GitHub API request failed: {type(exc).__name__}") from None
                time.sleep(min(2**attempt, 4))
        raise RuntimeError(type(last_error).__name__ if last_error else "GitHub API request failed")

    def _repo_url(self, suffix: str) -> str:
        return f"/repos/{self.repository}{suffix}"

    def temporary_release(self) -> dict[str, Any]:
        releases = self._request("GET", self._repo_url("/releases"), params={"per_page": 100}).json()
        for release in releases:
            if release.get("draft") and (
                release.get("tag_name") == TEMPORARY_RELEASE_NAME
                or release.get("name") == TEMPORARY_RELEASE_NAME
            ):
                return release
        return self._request(
            "POST",
            self._repo_url("/releases"),
            json={
                "tag_name": TEMPORARY_RELEASE_NAME,
                "name": TEMPORARY_RELEASE_NAME,
                "draft": True,
                "prerelease": False,
                "target_commitish": self.ref,
                "body": "Private temporary inputs for vid-pipeline. Never publish this release.",
            },
        ).json()

    def list_assets(self, release_id: int) -> list[dict[str, Any]]:
        return self._request(
            "GET", self._repo_url(f"/releases/{release_id}/assets"), params={"per_page": 100}
        ).json()

    def delete_asset(self, asset_id: int) -> None:
        self._request("DELETE", self._repo_url(f"/releases/assets/{asset_id}"))

    def upload_asset(self, request: GitHubRequest) -> None:
        path = Path(request.local_path)
        request.status = "uploading"
        request.upload_started_at = _now()
        self.state.save(request)
        release = self.temporary_release()
        request.release_id = int(release["id"])
        existing = next(
            (
                asset
                for asset in self.list_assets(request.release_id)
                if asset["name"] == request.safe_asset_name
            ),
            None,
        )
        if existing and int(existing.get("size", -1)) == request.file_size:
            request.asset_id = int(existing["id"])
            asset = existing
        else:
            if existing:
                self.delete_asset(int(existing["id"]))
            content_type = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
            upload_url = str(release["upload_url"]).split("{", 1)[0]
            with path.open("rb") as handle:
                response = self._request(
                    "POST",
                    upload_url,
                    params={"name": request.safe_asset_name, "label": request.sha256},
                    headers={
                        "Content-Type": content_type,
                        "Content-Length": str(request.file_size),
                    },
                    content=_ProgressFile(handle, request.file_size),
                )
            asset = response.json()
            if int(asset.get("size", -1)) != request.file_size:
                self.delete_asset(int(asset["id"]))
                raise RuntimeError("uploaded asset size mismatch")
            request.asset_id = int(asset["id"])
        public_url = asset.get("browser_download_url", "")
        if public_url:
            unauthenticated = self.public_http.get(public_url)
            if unauthenticated.status_code < 400:
                self.delete_asset(request.asset_id)
                request.asset_id = 0
                raise RuntimeError("Draft release asset was accessible without authentication.")
        request.status = "uploaded"
        request.upload_completed_at = _now()
        request.last_error = ""
        self.state.save(request)

    def dispatch_upload(self, request: GitHubRequest, options: dict[str, Any]) -> None:
        request.dispatch_id = uuid.uuid4().hex
        request.dispatch_started_at = _now()
        request.status = "dispatching"
        request.workflow_started_at = request.dispatch_started_at
        self.state.save(request)
        inputs = {
            "request_id": request.request_id,
            "asset_id": str(request.asset_id),
            "dispatch_id": request.dispatch_id,
            "original_name": request.original_name,
            "file_size": str(request.file_size),
            "sha256": request.sha256,
            "profile": options.get("profile", "balanced"),
            "model": options.get("model") or "",
            "language": options.get("language", "fa"),
            "no_editorial": str(options.get("no_editorial", True)).lower(),
        }
        response = self._request(
            "POST",
            self._repo_url(f"/actions/workflows/{UPLOAD_WORKFLOW}/dispatches"),
            json={"ref": self.ref, "inputs": inputs},
        )
        server_date = response.headers.get("Date", "")
        if server_date:
            try:
                parsed_server_date = parsedate_to_datetime(server_date)
                if parsed_server_date.tzinfo is None:
                    parsed_server_date = parsed_server_date.replace(tzinfo=UTC)
                request.dispatch_server_at = parsed_server_date.astimezone(UTC).isoformat()
            except (TypeError, ValueError, OverflowError):
                request.dispatch_server_at = ""
        if response.content:
            try:
                request.workflow_run_id = int(response.json().get("workflow_run_id", 0))
            except (TypeError, ValueError, json.JSONDecodeError):
                pass
        request.status = "queued"
        self.state.save(request)

    def dispatch_url(self, url: str, request: GitHubRequest, options: dict[str, Any]) -> None:
        request.workflow_name = URL_WORKFLOW
        request.status = "dispatching"
        request.workflow_started_at = _now()
        self.state.save(request)
        self._request(
            "POST",
            self._repo_url(f"/actions/workflows/{URL_WORKFLOW}/dispatches"),
            json={
                "ref": self.ref,
                "inputs": {
                    "url": url,
                    "request_id": request.request_id,
                    "profile": options.get("profile") or "balanced",
                    "whisper_model": options.get("model") or "",
                },
            },
        )
        request.status = "queued"
        self.state.save(request)

    def find_run(self, request: GitHubRequest) -> dict[str, Any] | None:
        if request.workflow_run_id:
            return self._request(
                "GET", self._repo_url(f"/actions/runs/{request.workflow_run_id}")
            ).json()
        runs = self._request(
            "GET",
            self._repo_url(f"/actions/workflows/{request.workflow_name}/runs"),
            params={"event": "workflow_dispatch", "branch": self.ref, "per_page": 50},
        ).json().get("workflow_runs", [])
        if not request.dispatch_id or not request.dispatch_started_at:
            return None
        reference_time = request.dispatch_server_at or request.dispatch_started_at
        try:
            dispatched_at = datetime.fromisoformat(reference_time.replace("Z", "+00:00"))
        except ValueError:
            return None
        earliest_allowed = dispatched_at - CLOCK_SKEW_TOLERANCE
        expected_title = (
            f"Uploaded video {request.request_id} — attempt {request.dispatch_id}"
        )
        for run in runs:
            created_at = str(run.get("created_at", ""))
            try:
                created = datetime.fromisoformat(created_at.replace("Z", "+00:00"))
            except ValueError:
                continue
            workflow_path = str(run.get("path", "")).split("@", 1)[0]
            if (
                run.get("event") != "workflow_dispatch"
                or run.get("head_branch") != self.ref
                or Path(workflow_path).name != request.workflow_name
                or run.get("display_title") != expected_title
                or created < earliest_allowed
            ):
                continue
            request.workflow_run_id = int(run["id"])
            request.workflow_run_url = run.get("html_url", "")
            self.state.save(request)
            return run
        return None

    def recover_dispatched_run(
        self, request: GitHubRequest, *, timeout: float = 60.0
    ) -> dict[str, Any] | None:
        deadline = time.monotonic() + timeout
        delay = 2.0
        while time.monotonic() < deadline:
            if run := self.find_run(request):
                return run
            time.sleep(delay)
            delay = min(delay * 1.5, 10.0)
        return None

    def _workflow_failure_detail(
        self, request: GitHubRequest, conclusion: str
    ) -> str:
        try:
            jobs = self._request(
                "GET",
                self._repo_url(
                    f"/actions/runs/{request.workflow_run_id}/jobs"
                ),
                params={"filter": "latest", "per_page": 100},
            ).json().get("jobs", [])
            for job in jobs:
                for step in job.get("steps", []):
                    if step.get("conclusion") == "failure":
                        name = str(step.get("name", "unknown"))[:300]
                        return f"workflow failure: step={name!r}; conclusion={conclusion}"
                if job.get("conclusion") == "failure":
                    name = str(job.get("name", "unknown"))[:300]
                    return f"workflow failure: job={name!r}; conclusion={conclusion}"
        except Exception:
            pass
        return f"workflow: {conclusion}"

    def wait(self, request: GitHubRequest, *, timeout: float = 6 * 3600) -> dict[str, Any]:
        deadline = time.monotonic() + timeout
        delay = 2.0
        while time.monotonic() < deadline:
            run = self.find_run(request)
            if run:
                request.status = "in_progress" if run["status"] != "completed" else request.status
                request.workflow_run_url = run.get("html_url", request.workflow_run_url)
                self.state.save(request)
                if run["status"] == "completed":
                    conclusion = run.get("conclusion") or "failure"
                    completed_at = run.get("updated_at") or run.get("run_completed_at")
                    request.workflow_completed_at = str(completed_at or _now())
                    request.status = (
                        "workflow_succeeded" if conclusion == "success" else "workflow_failed"
                    )
                    request.last_error = (
                        ""
                        if conclusion == "success"
                        else self._workflow_failure_detail(request, conclusion)
                    )
                    self.state.save(request)
                    return run
            time.sleep(delay)
            delay = min(delay * 1.5, 15)
        raise TimeoutError("GitHub workflow polling timed out.")

    def _artifact(self, request: GitHubRequest) -> dict[str, Any]:
        artifacts = self._request(
            "GET", self._repo_url(f"/actions/runs/{request.workflow_run_id}/artifacts")
        ).json().get("artifacts", [])
        expected = f"uploaded-transcript-{request.request_id}"
        if request.workflow_name == URL_WORKFLOW:
            matches = artifacts
        else:
            matches = [item for item in artifacts if item["name"] == expected]
        if not matches:
            raise RuntimeError("Result artifact was not found.")
        return matches[0]

    @staticmethod
    def _safe_extract(archive: Path, destination: Path) -> None:
        root = destination.resolve()
        with zipfile.ZipFile(archive) as bundle:
            for member in bundle.infolist():
                target = (destination / member.filename).resolve()
                if target != root and root not in target.parents:
                    raise ValueError("unsafe ZIP path")
                if member.is_dir():
                    target.mkdir(parents=True, exist_ok=True)
                    continue
                target.parent.mkdir(parents=True, exist_ok=True)
                with bundle.open(member) as source, target.open("wb") as output:
                    while chunk := source.read(1024 * 1024):
                        output.write(chunk)

    def download_and_validate(self, request: GitHubRequest) -> Path:
        artifact = self._artifact(request)
        request.artifact_id = int(artifact["id"])
        request.artifact_name = artifact["name"]
        request.status = "downloading"
        self.state.save(request)
        self.output_root.mkdir(parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile(suffix=".zip", delete=False) as temporary:
            archive = Path(temporary.name)
            with self.http.stream(
                "GET", self._repo_url(f"/actions/artifacts/{request.artifact_id}/zip")
            ) as response:
                response.raise_for_status()
                for chunk in response.iter_bytes(1024 * 1024):
                    temporary.write(chunk)
        staging = Path(tempfile.mkdtemp(prefix=".github-result-", dir=self.output_root))
        try:
            self._safe_extract(archive, staging)
            results = list(staging.rglob("result.json"))
            if not results:
                raise ValueError("Final transcript validation failed; result.json is missing.")
            result = json.loads(results[0].read_text(encoding="utf-8"))
            if str(result.get("status", "")).lower() in {"failed", "cancelled"}:
                raise ValueError("Final transcript validation failed; job failed.")
            job_root = results[0].parent
            transcript = job_root / "final" / "transcript.final.txt"
            if not transcript.is_file() or not transcript.read_text(encoding="utf-8").strip():
                raise ValueError("Final transcript validation failed; final text is empty.")
            request.job_id = str(result.get("job_id") or job_root.name)
            destination = self.output_root / request.job_id
            if destination.exists():
                import shutil

                shutil.rmtree(destination)
            job_root.replace(destination)
            request.output_path = str(destination)
            request.download_completed_at = _now()
            request.status = "validated"
            request.last_error = ""
            self.state.save(request)
            return destination
        finally:
            archive.unlink(missing_ok=True)
            if staging.exists():
                import shutil

                shutil.rmtree(staging, ignore_errors=True)

    def delete_result_artifact(self, request: GitHubRequest) -> None:
        if request.artifact_id:
            self._request(
                "DELETE", self._repo_url(f"/actions/artifacts/{request.artifact_id}")
            )

    def cleanup_request(self, request: GitHubRequest) -> None:
        if request.asset_id:
            try:
                self.delete_asset(request.asset_id)
            except Exception:
                request.status = "remote_cleanup_pending"
                request.last_error = "Remote cleanup is pending."
                self.state.save(request)
                raise
            request.asset_id = 0
        request.remote_deleted_at = _now()
        request.status = "completed"
        request.last_error = ""
        self.state.save(request)

    def create_file_request(self, path: Path) -> GitHubRequest:
        path = path.resolve()
        if not path.is_file() or path.suffix.lower() not in MEDIA_EXTENSIONS:
            raise ValueError(f"unsupported media file: {path}")
        size = path.stat().st_size
        if size >= MAX_ASSET_SIZE:
            raise ValueError(
                "File is too large for GitHub Release Asset upload. The file was not uploaded."
            )
        digest = sha256_file(path)
        previous = self.state.find_digest(digest, size)
        if previous and previous.status != "skipped":
            previous.local_path = str(path)
            self.state.save(previous)
            return previous
        request = GitHubRequest(
            request_id=uuid.uuid4().hex,
            local_path=str(path),
            original_name=path.name,
            safe_asset_name=safe_asset_name(path.name, digest),
            file_size=size,
            sha256=digest,
        )
        self.state.save(request)
        return request

    def process_file(
        self,
        path: Path,
        *,
        wait: bool = True,
        download: bool = True,
        delete_remote_after_success: bool = True,
        delete_result_artifact_after_download: bool = False,
        **options: Any,
    ) -> GitHubRequest:
        request = self.create_file_request(path)
        try:
            if request.status == "remote_cleanup_pending":
                self.cleanup_request(request)
                return request
            if not request.asset_id:
                self.upload_asset(request)
            if request.status == "workflow_failed":
                request.workflow_run_id = 0
                request.workflow_run_url = ""
                request.artifact_id = 0
                request.artifact_name = ""
                request.job_id = ""
                request.workflow_completed_at = ""
                request.last_error = ""
                request.status = "uploaded"
                self.state.save(request)
            if request.status == "dispatching" and not request.workflow_run_id:
                if not self.recover_dispatched_run(request):
                    request.last_error = (
                        "Dispatched workflow run has not appeared yet; "
                        "resume again without creating a duplicate run."
                    )
                    self.state.save(request)
                    return request
            elif request.status in {"queued", "in_progress"}:
                self.find_run(request)
            if not request.workflow_run_id and request.status in {
                "uploaded",
                "failed",
            }:
                self.dispatch_upload(request, options)
            if wait and request.status not in {"workflow_succeeded", "validated", "completed"}:
                run = self.wait(request)
                if run.get("conclusion") != "success":
                    return request
            if download and request.status == "workflow_succeeded":
                self.download_and_validate(request)
            if request.status == "validated" and delete_remote_after_success:
                self.cleanup_request(request)
            if (
                request.status == "completed"
                and delete_result_artifact_after_download
                and request.artifact_id
            ):
                self.delete_result_artifact(request)
            return request
        except Exception as exc:
            request.retry_count += 1
            request.last_error = str(exc)
            if request.status not in {"remote_cleanup_pending", "workflow_failed"}:
                request.status = "failed"
            self.state.save(request)
            raise

    def stale_assets(self, older_than_hours: int = 24) -> Iterable[dict[str, Any]]:
        release = self.temporary_release()
        cutoff = datetime.now(UTC) - timedelta(hours=older_than_hours)
        for asset in self.list_assets(int(release["id"])):
            created = datetime.fromisoformat(asset["created_at"].replace("Z", "+00:00"))
            if created < cutoff:
                yield asset


def client_from_args(args: Any) -> GitHubClient:
    token = os.getenv("VID_PIPELINE_GITHUB_TOKEN", "")
    repository = getattr(args, "repo", "") or detect_repository()
    ref = getattr(args, "ref", "") or os.getenv("VID_PIPELINE_GITHUB_REF", "main")
    return GitHubClient(token, repository, ref=ref, output_root=args.output_root)
