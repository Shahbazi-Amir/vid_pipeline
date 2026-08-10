"""Verified Aparat ingest without depending on the yt-dlp Aparat extractor."""

from __future__ import annotations

import hashlib
import json
import os
import re
import socket
import time
import urllib.error
import urllib.request
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, BinaryIO
from urllib.parse import urlparse

from vid_pipeline.audio import probe_media

APARAT_VIDEO_API = "https://www.aparat.com/etc/api/video/videohash/{uid}"
DEFAULT_MEDIA_PROFILE = "360p"
_UID_RE = re.compile(r"^[A-Za-z0-9]+$")
_TRANSIENT_HTTP_STATUS = {429, 500, 502, 503, 504}


class AparatIngestError(RuntimeError):
    """Base class for errors at the explicit Aparat ingest boundary."""


class AparatPermanentError(AparatIngestError):
    """The mapping or API schema cannot be handled safely and must not retry."""


class AparatTransientError(AparatIngestError):
    """A bounded retry may recover this network failure."""


@dataclass(frozen=True, slots=True)
class ResolvedAparatMedia:
    source_url: str
    uid: str
    title: str
    duration_seconds: float
    profile: str
    resolver_type: str
    direct_url: str = field(repr=False)


def _uid_from_page_url(page_url: str) -> str:
    parsed = urlparse(page_url)
    if parsed.scheme != "https" or parsed.hostname not in {"aparat.com", "www.aparat.com"}:
        raise AparatPermanentError("Aparat source page URL is invalid")
    parts = [part for part in parsed.path.split("/") if part]
    if len(parts) != 2 or parts[0] != "v" or not _UID_RE.fullmatch(parts[1]):
        raise AparatPermanentError("Aparat source page URL does not contain a valid video uid")
    return parts[1]


def _default_json_request(url: str, timeout: float) -> Any:
    request = urllib.request.Request(
        url,
        headers={
            "Accept": "application/json",
            "User-Agent": "Mozilla/5.0 vid-pipeline-aparat-ingest/1.0",
        },
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return json.load(response)


def _network_error_kind(exc: BaseException) -> str | None:
    if isinstance(exc, urllib.error.HTTPError):
        return f"http_{exc.code}" if exc.code in _TRANSIENT_HTTP_STATUS else None
    if isinstance(exc, (TimeoutError, socket.timeout, ConnectionResetError)):
        return type(exc).__name__.lower()
    if isinstance(exc, urllib.error.URLError):
        reason = exc.reason
        if isinstance(reason, (TimeoutError, socket.timeout, ConnectionResetError, OSError)):
            return type(reason).__name__.lower()
    return None


def _candidate_profile(value: object) -> int | None:
    match = re.fullmatch(r"(\d{2,4})p", str(value or "").strip().lower())
    return int(match.group(1)) if match else None


def _select_media(video: dict[str, Any], preferred_profile: str) -> tuple[str, str]:
    rows = video.get("file_link_all")
    if not isinstance(rows, list):
        raise AparatPermanentError("Aparat API schema is missing file_link_all")

    candidates: list[tuple[int, str, str]] = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        profile = str(row.get("profile") or "").strip().lower()
        resolution = _candidate_profile(profile)
        urls = row.get("urls")
        if resolution is None or not isinstance(urls, list):
            continue
        direct = next((item for item in urls if isinstance(item, str) and item.startswith("https://")), "")
        if not direct:
            continue
        parsed = urlparse(direct)
        host = (parsed.hostname or "").lower()
        if not (host == "aparat.com" or host.endswith(".aparat.com") or host.endswith(".aparat.cloud")):
            continue
        candidates.append((resolution, profile, direct))

    if not candidates:
        raise AparatPermanentError("Aparat API returned no supported downloadable media")
    preferred = _candidate_profile(preferred_profile) or 360
    exact = next((item for item in candidates if item[0] == preferred), None)
    selected = exact or min(candidates, key=lambda item: (abs(item[0] - preferred), item[0]))
    return selected[1], selected[2]


def resolve_aparat_media(
    page_url: str,
    *,
    expected_uid: str | None = None,
    preferred_profile: str = DEFAULT_MEDIA_PROFILE,
    attempts: int = 3,
    timeout: float = 45.0,
    request_json: Callable[[str, float], Any] = _default_json_request,
    sleep: Callable[[float], None] = time.sleep,
) -> ResolvedAparatMedia:
    """Resolve a verified public page to one direct URL without logging that URL."""

    if attempts < 1:
        raise ValueError("attempts must be at least 1")
    uid = _uid_from_page_url(page_url)
    if expected_uid is not None and uid != expected_uid:
        raise AparatPermanentError("Aparat manifest uid does not match its source page URL")

    payload: Any = None
    for attempt in range(1, attempts + 1):
        try:
            payload = request_json(APARAT_VIDEO_API.format(uid=uid), timeout)
            break
        except json.JSONDecodeError as exc:
            raise AparatPermanentError("Aparat API returned invalid JSON") from exc
        except Exception as exc:
            kind = _network_error_kind(exc)
            if kind is None:
                if isinstance(exc, urllib.error.HTTPError):
                    raise AparatPermanentError(
                        f"Aparat API rejected the video request (HTTP {exc.code})"
                    ) from None
                raise AparatPermanentError(
                    f"Aparat resolver failed permanently ({type(exc).__name__})"
                ) from None
            if attempt == attempts:
                raise AparatTransientError(
                    f"Aparat API remained unavailable after {attempts} attempts ({kind})"
                ) from None
            sleep(float(2 ** (attempt - 1)))

    if not isinstance(payload, dict) or not isinstance(payload.get("video"), dict):
        raise AparatPermanentError("Aparat API schema is missing the video object")
    video = payload["video"]
    returned_uid = str(video.get("uid") or "").strip()
    if returned_uid != uid:
        raise AparatPermanentError("Aparat API video uid does not match the verified mapping")
    if str(video.get("process") or "").strip().lower() not in {"", "done"}:
        raise AparatPermanentError("Aparat video is not in a downloadable completed state")

    profile, direct_url = _select_media(video, preferred_profile)
    try:
        duration = float(video.get("duration") or 0)
    except (TypeError, ValueError):
        duration = 0.0
    if duration <= 0:
        raise AparatPermanentError("Aparat API video duration is missing or invalid")
    return ResolvedAparatMedia(
        source_url=page_url,
        uid=uid,
        title=str(video.get("title") or "").strip(),
        duration_seconds=duration,
        profile=profile,
        resolver_type="aparat-official-video-api-v1",
        direct_url=direct_url,
    )


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _probe_summary(path: Path) -> tuple[dict[str, Any], float]:
    started = time.monotonic()
    probe = probe_media(path)
    elapsed = time.monotonic() - started
    streams = probe.get("streams") or []
    audio = next((row for row in streams if row.get("codec_type") == "audio"), {})
    video = next((row for row in streams if row.get("codec_type") == "video"), {})
    fmt = probe.get("format") or {}
    try:
        duration = float(fmt.get("duration") or 0)
    except (TypeError, ValueError):
        duration = 0.0
    if duration <= 0 or not audio:
        raise AparatPermanentError("ffprobe rejected the downloaded Aparat media")
    return {
        "duration_seconds": duration,
        "container": str(fmt.get("format_name") or ""),
        "audio_codec": str(audio.get("codec_name") or ""),
        "video_codec": str(video.get("codec_name") or ""),
    }, elapsed


def _default_media_open(url: str, timeout: float) -> BinaryIO:
    request = urllib.request.Request(
        url,
        headers={"User-Agent": "Mozilla/5.0 vid-pipeline-aparat-ingest/1.0"},
    )
    return urllib.request.urlopen(request, timeout=timeout)


def download_verified_media(
    resolved: ResolvedAparatMedia,
    destination: Path,
    *,
    attempts: int = 3,
    timeout: float = 120.0,
    open_media: Callable[[str, float], BinaryIO] = _default_media_open,
    sleep: Callable[[float], None] = time.sleep,
) -> dict[str, Any]:
    """Download once to .part, validate, then atomically expose the final file."""

    if attempts < 1:
        raise ValueError("attempts must be at least 1")
    destination.parent.mkdir(parents=True, exist_ok=True)
    part = destination.with_name(destination.name + ".part")
    download_started = time.monotonic()
    content_length = 0
    for attempt in range(1, attempts + 1):
        part.unlink(missing_ok=True)
        try:
            with open_media(resolved.direct_url, timeout) as response, part.open("wb") as handle:
                headers = getattr(response, "headers", {})
                raw_length = headers.get("Content-Length") if hasattr(headers, "get") else None
                content_length = int(raw_length) if raw_length and str(raw_length).isdigit() else 0
                while True:
                    block = response.read(1024 * 1024)
                    if not block:
                        break
                    handle.write(block)
                handle.flush()
                os.fsync(handle.fileno())
            size = part.stat().st_size
            if size <= 0 or (content_length and size != content_length):
                raise AparatTransientError("Aparat media download was incomplete")
            break
        except AparatTransientError:
            if attempt == attempts:
                part.unlink(missing_ok=True)
                raise
            sleep(float(2 ** (attempt - 1)))
        except Exception as exc:
            kind = _network_error_kind(exc)
            if kind is None:
                part.unlink(missing_ok=True)
                raise AparatPermanentError(
                    f"Aparat media download failed permanently ({type(exc).__name__})"
                ) from None
            if attempt == attempts:
                part.unlink(missing_ok=True)
                raise AparatTransientError(
                    f"Aparat media download failed after {attempts} attempts ({kind})"
                ) from None
            sleep(float(2 ** (attempt - 1)))

    download_seconds = time.monotonic() - download_started
    try:
        probe, ffprobe_seconds = _probe_summary(part)
        size = part.stat().st_size
        digest = _sha256(part)
    except Exception:
        part.unlink(missing_ok=True)
        raise
    part.replace(destination)
    throughput = size / (1024 * 1024) / download_seconds if download_seconds > 0 else 0.0
    return {
        "media_path": str(destination.resolve()),
        "media_size_bytes": size,
        "media_sha256": digest,
        **probe,
        "download_seconds": round(download_seconds, 6),
        "download_mib_per_second": round(throughput, 6),
        "ffprobe_seconds": round(ffprobe_seconds, 6),
        "reused_verified_media": False,
    }


def validate_verified_media(path: Path, metadata: dict[str, Any]) -> dict[str, Any] | None:
    if not path.is_file() or path.stat().st_size <= 0:
        return None
    if int(metadata.get("media_size_bytes") or 0) != path.stat().st_size:
        return None
    expected = str(metadata.get("media_sha256") or "")
    if not expected or _sha256(path) != expected:
        return None
    probe, ffprobe_seconds = _probe_summary(path)
    return {**metadata, **probe, "ffprobe_seconds": round(ffprobe_seconds, 6)}


def ensure_verified_aparat_media(
    page_url: str,
    destination: Path,
    metadata_path: Path,
    *,
    expected_uid: str | None = None,
    preferred_profile: str = DEFAULT_MEDIA_PROFILE,
) -> dict[str, Any]:
    """Reuse a checksum-verified local file, otherwise resolve and download exactly once."""

    if metadata_path.is_file():
        try:
            prior = json.loads(metadata_path.read_text(encoding="utf-8"))
            if prior.get("source_url") == page_url:
                validated = validate_verified_media(destination, prior)
                if validated is not None:
                    result = {
                        **validated,
                        "resolve_seconds": 0.0,
                        "download_seconds": 0.0,
                        "download_mib_per_second": 0.0,
                        "reused_verified_media": True,
                    }
                    return result
        except (OSError, ValueError, json.JSONDecodeError, AparatIngestError):
            pass

    resolve_started = time.monotonic()
    resolved = resolve_aparat_media(
        page_url,
        expected_uid=expected_uid,
        preferred_profile=preferred_profile,
    )
    resolve_seconds = time.monotonic() - resolve_started
    downloaded = download_verified_media(resolved, destination)
    payload = {
        "schema_version": 1,
        "episode_source": "verified_manifest",
        "source_url": page_url,
        "uid": resolved.uid,
        "title": resolved.title,
        "resolver_type": resolved.resolver_type,
        "media_profile": resolved.profile,
        "resolve_seconds": round(resolve_seconds, 6),
        **downloaded,
    }
    metadata_path.parent.mkdir(parents=True, exist_ok=True)
    temporary = metadata_path.with_suffix(metadata_path.suffix + ".tmp")
    temporary.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temporary.replace(metadata_path)
    return payload
