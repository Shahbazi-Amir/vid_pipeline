"""Video metadata extraction and download through yt-dlp."""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

from vid_pipeline.errors import ExternalToolError

_CERTIFICATE_ERROR_MARKERS = (
    "certificate_verify_failed",
    "certificate verify failed",
    "hostname mismatch",
)
_TRANSIENT_ERROR_MARKERS = (
    "timed out",
    "timeout",
    "temporarily unavailable",
    "connection reset",
    "remote end closed connection",
    "http error 429",
    "http error 500",
    "http error 502",
    "http error 503",
    "http error 504",
)


def _yt_dlp_module():
    try:
        import yt_dlp
    except ImportError as exc:
        raise ExternalToolError(
            "yt-dlp is not installed. Run: pip install -e '.[download]'"
        ) from exc
    return yt_dlp


def _is_certificate_error(error: Exception) -> bool:
    message = str(error).casefold()
    return any(marker in message for marker in _CERTIFICATE_ERROR_MARKERS)


def _is_transient_error(error: Exception) -> bool:
    message = str(error).casefold()
    return any(marker in message for marker in _TRANSIENT_ERROR_MARKERS)


def _extract_info(
    yt_dlp: Any,
    url: str,
    options: dict[str, Any],
    *,
    download: bool,
    attempts: int = 3,
) -> dict[str, Any]:
    """Extract sanitized info with narrow retries for certificate and transient failures."""

    if attempts < 1:
        raise ValueError("attempts must be at least 1")

    current_options = options.copy()
    last_error: Exception | None = None

    for attempt in range(attempts):
        try:
            with yt_dlp.YoutubeDL(current_options) as downloader:
                info = downloader.extract_info(url, download=download)
                return downloader.sanitize_info(info)
        except Exception as exc:
            last_error = exc
            if _is_certificate_error(exc) and not current_options.get("nocheckcertificate"):
                current_options = {**current_options, "nocheckcertificate": True}
                continue
            if _is_transient_error(exc) and attempt + 1 < attempts:
                time.sleep(2**attempt)
                continue
            raise

    if last_error is not None:
        raise last_error
    raise RuntimeError("yt-dlp extraction failed without an error")


def extract_metadata(url: str) -> dict[str, Any]:
    yt_dlp = _yt_dlp_module()
    options = {
        "quiet": True,
        "no_warnings": True,
        "noplaylist": True,
        "skip_download": True,
        "socket_timeout": 120,
        "extractor_retries": 5,
        "source_address": "0.0.0.0",
    }
    try:
        return _extract_info(yt_dlp, url, options, download=False)
    except Exception as exc:
        raise ExternalToolError(f"yt-dlp could not inspect the source: {exc}") from exc


def download_video(url: str, output_dir: str | Path) -> tuple[Path, dict[str, Any]]:
    yt_dlp = _yt_dlp_module()
    destination = Path(output_dir)
    destination.mkdir(parents=True, exist_ok=True)
    options = {
        "format": "bestvideo*+bestaudio/best",
        "outtmpl": str(destination / "video.%(ext)s"),
        "merge_output_format": "mp4",
        "noplaylist": True,
        "continuedl": True,
        "overwrites": False,
        "retries": 10,
        "fragment_retries": 10,
        "extractor_retries": 5,
        "socket_timeout": 120,
        "source_address": "0.0.0.0",
        "quiet": False,
        "writeinfojson": False,
    }
    try:
        sanitized = _extract_info(yt_dlp, url, options, download=True)
        requested = sanitized.get("requested_downloads") or []
        filename = sanitized.get("_filename")
        candidates = [
            Path(item.get("filepath", ""))
            for item in requested
            if item.get("filepath")
        ]
        if filename:
            candidates.append(Path(filename))
        candidates.extend(destination.glob("video.*"))
        video = next((item for item in candidates if item.exists() and item.is_file()), None)
        if video is None:
            raise ExternalToolError("Download completed but no video file was found.")
        metadata_path = destination.parent / "video-info.json"
        metadata_path.write_text(
            json.dumps(sanitized, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        return video, sanitized
    except ExternalToolError:
        raise
    except Exception as exc:
        raise ExternalToolError(f"Video download failed: {exc}") from exc
