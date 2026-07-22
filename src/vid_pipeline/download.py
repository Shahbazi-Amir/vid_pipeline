"""Video metadata extraction and download through yt-dlp."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from vid_pipeline.errors import ExternalToolError


def _yt_dlp_module():
    try:
        import yt_dlp
    except ImportError as exc:
        raise ExternalToolError(
            "yt-dlp is not installed. Run: pip install -e '.[download]'"
        ) from exc
    return yt_dlp


def extract_metadata(url: str, *, no_check_certificate: bool = False) -> dict[str, Any]:
    yt_dlp = _yt_dlp_module()
    options = {
        "quiet": True,
        "no_warnings": True,
        "noplaylist": True,
        "skip_download": True,
        "nocheckcertificate": no_check_certificate,
    }
    try:
        with yt_dlp.YoutubeDL(options) as downloader:
            info = downloader.extract_info(url, download=False)
            return downloader.sanitize_info(info)
    except Exception as exc:
        raise ExternalToolError(f"yt-dlp could not inspect the source: {exc}") from exc


def download_video(
    url: str,
    output_dir: str | Path,
    *,
    no_check_certificate: bool = False,
) -> tuple[Path, dict[str, Any]]:
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
        "quiet": False,
        "writeinfojson": False,
        "nocheckcertificate": no_check_certificate,
    }
    try:
        with yt_dlp.YoutubeDL(options) as downloader:
            info = downloader.extract_info(url, download=True)
            sanitized = downloader.sanitize_info(info)
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
