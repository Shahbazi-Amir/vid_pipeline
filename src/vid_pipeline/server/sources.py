"""Input source adapters for upload, public URL and GitHub Release assets."""

from __future__ import annotations

import hashlib
import ipaddress
import json
import os
import re
import socket
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any, Callable

from vid_pipeline.download import download_video
from vid_pipeline.server.repository import Repository
from vid_pipeline.server.storage import ObjectStore

REPOSITORY_RE = re.compile(r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$")
BLOCKED_HOSTS = {"localhost", "metadata.google.internal", "metadata", "host.docker.internal"}


def _public_ip(value: str) -> bool:
    try:
        address = ipaddress.ip_address(value)
    except ValueError:
        return False
    return bool(address.is_global)


def validate_public_url(
    url: str,
    *,
    resolve_dns: bool = True,
    resolver: Callable[..., Any] = socket.getaddrinfo,
) -> str:
    parsed = urllib.parse.urlparse(str(url).strip())
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        raise ValueError("source URL must be an http or https URL")
    if parsed.username or parsed.password:
        raise ValueError("credentials in source URLs are forbidden")
    hostname = parsed.hostname.rstrip(".").casefold()
    if hostname in BLOCKED_HOSTS or hostname.endswith(".local") or hostname.endswith(".internal"):
        raise ValueError("private/internal source URL is forbidden")
    try:
        direct = ipaddress.ip_address(hostname)
    except ValueError:
        direct = None
    if direct is not None and not direct.is_global:
        raise ValueError("private/non-public source IP is forbidden")
    if resolve_dns and direct is None:
        try:
            rows = resolver(hostname, parsed.port or (443 if parsed.scheme == "https" else 80), type=socket.SOCK_STREAM)
        except OSError as exc:
            raise ValueError(f"source hostname could not be resolved: {hostname}") from exc
        addresses = {str(row[4][0]) for row in rows}
        if not addresses or any(not _public_ip(value) for value in addresses):
            raise ValueError("source hostname resolves to a private/non-public IP")
    return urllib.parse.urlunparse(parsed)


def normalize_source_request(payload: dict[str, Any], repository: Repository) -> dict[str, Any]:
    source = payload.get("source")
    if not isinstance(source, dict):
        source = {"type": "upload", "upload_id": str(payload.get("upload_id", ""))}
    source_type = str(source.get("type") or "").strip().lower()
    if source_type == "upload":
        upload_id = str(source.get("upload_id") or payload.get("upload_id") or "")
        upload = repository.upload(upload_id)
        if not upload or upload.get("status") != "uploaded":
            raise ValueError("upload is not complete")
        return {
            "type": "upload",
            "upload_id": upload_id,
            "file_name": upload["file_name"],
            "file_size": upload["file_size"],
            "sha256": upload["sha256"],
            "object_key": upload["object_key"],
        }
    if source_type == "url":
        return {
            "type": "url",
            "url": validate_public_url(str(source.get("url") or ""), resolve_dns=False),
        }
    if source_type == "github_release":
        repository_name = str(source.get("repository") or "").strip()
        tag = str(source.get("tag") or "").strip()
        asset = Path(str(source.get("asset") or "")).name
        if not REPOSITORY_RE.fullmatch(repository_name):
            raise ValueError("GitHub release repository must use owner/name")
        if not tag or len(tag) > 200:
            raise ValueError("GitHub release tag is required")
        if not asset or asset in {".", ".."}:
            raise ValueError("GitHub release asset name is required")
        return {
            "type": "github_release",
            "repository": repository_name,
            "tag": tag,
            "asset": asset,
        }
    raise ValueError("source.type must be upload, url, or github_release")


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


class SourceMaterializer:
    def __init__(
        self,
        repository: Repository,
        storage: ObjectStore,
        *,
        opener: Callable[..., Any] = urllib.request.urlopen,
        url_downloader: Callable[..., Any] = download_video,
    ) -> None:
        self.repository = repository
        self.storage = storage
        self.opener = opener
        self.url_downloader = url_downloader

    def materialize(self, job: dict[str, Any], work: Path) -> Path:
        source = job.get("source") or {
            "type": "upload",
            "upload_id": job.get("upload_id", ""),
        }
        source_type = source.get("type")
        if source_type == "upload":
            upload = self.repository.upload(str(source.get("upload_id") or ""))
            if not upload or upload.get("status") != "uploaded":
                raise ValueError("uploaded input is unavailable")
            destination = work / "source" / "upload" / Path(str(upload["file_name"])).name
            path = self.storage.materialize(str(upload["object_key"]), destination)
            if not path.is_file():
                raise ValueError("uploaded input object is unavailable")
            if int(upload.get("file_size") or 0) and path.stat().st_size != int(upload["file_size"]):
                raise ValueError("materialized uploaded input size mismatch")
            if str(upload.get("sha256") or "") and _sha256(path) != str(upload["sha256"]):
                raise ValueError("materialized uploaded input SHA-256 mismatch")
            self._stamp(job, source_type, path, {"upload_id": upload["upload_id"]})
            return path
        if source_type == "url":
            url = validate_public_url(str(source.get("url") or ""), resolve_dns=True)
            directory = work / "source" / "url"
            directory.mkdir(parents=True, exist_ok=True)
            media, metadata = self.url_downloader(url, directory)
            media = Path(media)
            self._stamp(
                job,
                source_type,
                media,
                {"url": url, "title": str((metadata or {}).get("title") or "")},
            )
            return media
        if source_type == "github_release":
            return self._github_release(job, source, work)
        raise ValueError(f"unsupported source type: {source_type!r}")

    def _github_headers(self, accept: str) -> dict[str, str]:
        headers = {
            "Accept": accept,
            "User-Agent": "vid-pipeline",
            "X-GitHub-Api-Version": "2022-11-28",
        }
        token = os.getenv("VID_PIPELINE_GITHUB_TOKEN", "").strip()
        if token:
            headers["Authorization"] = f"Bearer {token}"
        return headers

    def _github_release(self, job: dict[str, Any], source: dict[str, Any], work: Path) -> Path:
        repository_name = str(source["repository"])
        tag = str(source["tag"])
        asset_name = Path(str(source["asset"])).name
        release_url = (
            "https://api.github.com/repos/"
            + repository_name
            + "/releases/tags/"
            + urllib.parse.quote(tag, safe="")
        )
        request = urllib.request.Request(
            release_url,
            headers=self._github_headers("application/vnd.github+json"),
        )
        with self.opener(request, timeout=60) as response:
            release = json.loads(response.read().decode("utf-8"))
        asset = next(
            (item for item in release.get("assets") or [] if item.get("name") == asset_name),
            None,
        )
        if not asset:
            raise ValueError(f"GitHub release asset not found: {asset_name}")
        declared_size = int(asset.get("size") or 0)
        max_size = int(os.getenv("VID_PIPELINE_MAX_FILE_SIZE", str(50 * 1024**3)))
        if declared_size and declared_size > max_size:
            raise ValueError("GitHub release asset exceeds maximum file size")
        asset_api_url = str(asset.get("url") or "")
        if not asset_api_url.startswith("https://api.github.com/"):
            raise ValueError("GitHub release returned an unsafe asset API URL")
        target = work / "source" / "github-release" / asset_name
        target.parent.mkdir(parents=True, exist_ok=True)
        request = urllib.request.Request(
            asset_api_url,
            headers=self._github_headers("application/octet-stream"),
        )
        total = 0
        with self.opener(request, timeout=120) as response, target.open("wb") as output:
            while chunk := response.read(1024 * 1024):
                total += len(chunk)
                if total > max_size:
                    target.unlink(missing_ok=True)
                    raise ValueError("GitHub release asset exceeds maximum file size")
                output.write(chunk)
        if declared_size and total != declared_size:
            target.unlink(missing_ok=True)
            raise ValueError("GitHub release asset size mismatch")
        self._stamp(
            job,
            "github_release",
            target,
            {
                "repository": repository_name,
                "tag": tag,
                "asset": asset_name,
                "release_id": release.get("id"),
                "asset_id": asset.get("id"),
            },
        )
        return target

    @staticmethod
    def _stamp(job: dict[str, Any], source_type: str, path: Path, details: dict[str, Any]) -> None:
        job["source_materialization"] = {
            "type": source_type,
            "path": str(path),
            "file_name": path.name,
            "file_size": path.stat().st_size,
            "sha256": _sha256(path),
            **details,
        }
