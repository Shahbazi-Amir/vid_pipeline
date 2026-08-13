"""Deterministic public/private GitHub Release media ingestion."""

from __future__ import annotations

import hashlib
import json
import os
import re
import urllib.error
import urllib.parse
import urllib.request
import uuid
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from vid_pipeline.errors import PipelineError
from vid_pipeline.media import MEDIA_EXTENSIONS

GITHUB_API = "https://api.github.com"
DEFAULT_MAX_BYTES = 2 * 1024 * 1024 * 1024
_REPOSITORY = re.compile(r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$")


@dataclass(frozen=True, slots=True)
class ReleaseAsset:
    repository: str
    tag: str
    release_id: int
    release_name: str
    asset_id: int
    asset_name: str
    size: int
    digest: str
    browser_download_url: str

    def provenance(self) -> dict[str, Any]:
        return {"source": "github_release", **asdict(self)}


def _headers(token: str, *, binary: bool = False) -> dict[str, str]:
    headers = {
        "Accept": "application/octet-stream" if binary else "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
        "User-Agent": "vid-pipeline-release-source",
    }
    if token:
        headers["Authorization"] = f"Bearer {token}"
    return headers


def _request_json(url: str, token: str, timeout: float) -> Any:
    request = urllib.request.Request(url, headers=_headers(token))
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return json.load(response)
    except urllib.error.HTTPError as exc:
        hint = {
            401: "GitHub authentication was rejected",
            403: "GitHub denied access or rate-limited the request",
            404: "GitHub release or asset was not found",
        }.get(exc.code, "GitHub API request failed")
        raise PipelineError(f"{hint} (HTTP {exc.code}).") from None
    except (OSError, json.JSONDecodeError) as exc:
        raise PipelineError(f"GitHub API request failed: {type(exc).__name__}.") from None


def resolve_release_asset(
    repository: str,
    tag: str,
    *,
    asset_name: str = "",
    asset_id: int = 0,
    token: str = "",
    timeout: float = 60,
) -> ReleaseAsset:
    """Resolve exactly one uploaded media asset without fuzzy matching."""
    if not _REPOSITORY.fullmatch(repository):
        raise ValueError("repository must use the owner/name form")
    if not tag.strip():
        raise ValueError("release tag is required")
    if bool(asset_name) == bool(asset_id):
        raise ValueError("provide exactly one of asset_name or asset_id")

    encoded_tag = urllib.parse.quote(tag, safe="")
    release = _request_json(
        f"{GITHUB_API}/repos/{repository}/releases/tags/{encoded_tag}", token, timeout
    )
    assets = release.get("assets") or []
    candidates = [
        item
        for item in assets
        if item.get("state") == "uploaded"
        and (
            (asset_id and int(item.get("id") or 0) == asset_id)
            or (asset_name and str(item.get("name") or "") == asset_name)
        )
    ]
    if len(candidates) != 1:
        selector = f"id {asset_id}" if asset_id else repr(asset_name)
        raise PipelineError(f"Release asset {selector} did not resolve to exactly one uploaded asset.")
    asset = candidates[0]
    name = Path(str(asset.get("name") or "")).name
    if not name or name != str(asset.get("name") or ""):
        raise PipelineError("GitHub release asset has an unsafe filename.")
    if Path(name).suffix.casefold() not in MEDIA_EXTENSIONS:
        raise PipelineError(f"Unsupported release media extension: {Path(name).suffix or '(none)'}")
    size = int(asset.get("size") or 0)
    if size <= 0:
        raise PipelineError("GitHub release asset is empty.")
    return ReleaseAsset(
        repository=repository,
        tag=str(release.get("tag_name") or tag),
        release_id=int(release["id"]),
        release_name=str(release.get("name") or ""),
        asset_id=int(asset["id"]),
        asset_name=name,
        size=size,
        digest=str(asset.get("digest") or ""),
        browser_download_url=str(asset.get("browser_download_url") or ""),
    )


def download_release_asset(
    asset: ReleaseAsset,
    destination_root: str | Path,
    *,
    token: str = "",
    timeout: float = 120,
    max_bytes: int = DEFAULT_MAX_BYTES,
) -> Path:
    """Download an asset atomically and verify its advertised size and digest."""
    if asset.size > max_bytes:
        raise PipelineError(f"Release asset exceeds the {max_bytes}-byte download limit.")
    repository_path = Path(*asset.repository.split("/"))
    target = Path(destination_root) / repository_path / str(asset.release_id) / asset.asset_name
    cache_metadata = target.with_name(f"{target.name}.cache.json")
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.is_file() and target.stat().st_size == asset.size:
        actual_sha256 = _sha256(target)
        if asset.digest.startswith("sha256:") and actual_sha256 == asset.digest.removeprefix(
            "sha256:"
        ):
            return target
        if not asset.digest and _cache_matches(cache_metadata, asset, actual_sha256):
            return target

    temporary = target.with_name(f".{target.name}.{uuid.uuid4().hex}.part")
    url = f"{GITHUB_API}/repos/{asset.repository}/releases/assets/{asset.asset_id}"
    request = urllib.request.Request(url, headers=_headers(token, binary=True))
    received = 0
    digest = hashlib.sha256()
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response, temporary.open("wb") as out:
            while chunk := response.read(1024 * 1024):
                received += len(chunk)
                if received > max_bytes or received > asset.size:
                    raise PipelineError("Release asset exceeded its declared or configured size.")
                digest.update(chunk)
                out.write(chunk)
        if received != asset.size:
            raise PipelineError("Downloaded release asset size does not match GitHub metadata.")
        actual_digest = digest.hexdigest()
        if asset.digest.startswith("sha256:") and actual_digest != asset.digest.removeprefix(
            "sha256:"
        ):
            raise PipelineError("Downloaded release asset SHA-256 does not match GitHub metadata.")
        temporary.replace(target)
        _write_cache_metadata(cache_metadata, asset, actual_digest)
        return target
    except urllib.error.HTTPError as exc:
        raise PipelineError(f"GitHub release asset download failed (HTTP {exc.code}).") from None
    except OSError as exc:
        raise PipelineError(f"GitHub release asset download failed: {type(exc).__name__}.") from None
    finally:
        temporary.unlink(missing_ok=True)


def token_from_environment() -> str:
    """Read a token without ever serializing it into provenance."""
    return (
        os.getenv("VID_PIPELINE_RELEASE_TOKEN", "").strip()
        or os.getenv("GITHUB_TOKEN", "").strip()
        or os.getenv("GH_TOKEN", "").strip()
    )


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _cache_identity(asset: ReleaseAsset) -> dict[str, Any]:
    return {
        "schema_version": 1,
        "repository": asset.repository,
        "release_id": asset.release_id,
        "asset_id": asset.asset_id,
        "asset_name": asset.asset_name,
        "size": asset.size,
        "github_digest": asset.digest,
    }


def _cache_matches(path: Path, asset: ReleaseAsset, actual_sha256: str) -> bool:
    """Trust digest-less cache only when its complete identity and local hash match."""
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return False
    expected = _cache_identity(asset)
    return all(payload.get(key) == value for key, value in expected.items()) and payload.get(
        "sha256"
    ) == actual_sha256


def _write_cache_metadata(path: Path, asset: ReleaseAsset, sha256: str) -> None:
    temporary = path.with_name(f".{path.name}.{uuid.uuid4().hex}.tmp")
    payload = {**_cache_identity(asset), "sha256": sha256}
    try:
        temporary.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
        temporary.replace(path)
    finally:
        temporary.unlink(missing_ok=True)
