"""Shared media discovery and FFprobe-based validation."""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path
from typing import Any

from vid_pipeline.errors import ExternalToolError

VIDEO_EXTENSIONS = frozenset({".avi", ".m4v", ".mkv", ".mov", ".mp4"})
AUDIO_EXTENSIONS = frozenset(
    {".aac", ".ac3", ".aif", ".aiff", ".alac", ".amr", ".caf", ".flac",
     ".m4a", ".mp3", ".ogg", ".opus", ".wav", ".webm", ".wma"}
)
MEDIA_EXTENSIONS = VIDEO_EXTENSIONS | AUDIO_EXTENSIONS


def discover_media(path: Path, recursive: bool = False) -> list[Path]:
    """Discover likely media; decoding is still verified by the worker."""
    iterator = path.rglob("*") if recursive else path.glob("*")
    return sorted(
        item.resolve() for item in iterator
        if item.is_file() and item.suffix.casefold() in MEDIA_EXTENSIONS
    )


def probe_media(path: str | Path) -> dict[str, Any]:
    """Return normalized FFprobe metadata and a logical media type."""
    source = Path(path)
    if not source.is_file() or source.stat().st_size == 0:
        return {"input_type": "invalid", "error": "media file is missing or empty",
                "has_audio_stream": False, "has_video_stream": False,
                "has_attached_picture": False}
    ffprobe = shutil.which("ffprobe")
    if not ffprobe:
        raise ExternalToolError("Required tool 'ffprobe' was not found in PATH.")
    result = subprocess.run(
        [ffprobe, "-v", "error", "-show_entries",
         "format=format_name,duration,bit_rate:stream=codec_type,codec_name,sample_rate,channels,channel_layout,bit_rate:stream_disposition=attached_pic",
         "-of", "json", str(source)], capture_output=True, text=True, check=False,
    )
    if result.returncode:
        return {"input_type": "invalid", "error": result.stderr.strip() or "ffprobe failed",
                "has_audio_stream": False, "has_video_stream": False,
                "has_attached_picture": False}
    try:
        raw = json.loads(result.stdout)
    except json.JSONDecodeError:
        return {"input_type": "invalid", "error": "ffprobe returned invalid JSON",
                "has_audio_stream": False, "has_video_stream": False,
                "has_attached_picture": False}
    streams = raw.get("streams") or []
    audio = next((s for s in streams if s.get("codec_type") == "audio"), {})
    video_streams = [s for s in streams if s.get("codec_type") == "video"]
    attached_pictures = [
        stream for stream in video_streams
        if int((stream.get("disposition") or {}).get("attached_pic") or 0) == 1
    ]
    motion_video_streams = [stream for stream in video_streams if stream not in attached_pictures]
    has_audio = bool(audio)
    has_video = bool(motion_video_streams)
    has_attached_picture = bool(attached_pictures)
    input_type = "video" if has_video else "audio" if has_audio else "unknown"
    fmt = raw.get("format") or {}

    def number(value: Any, kind: type[int] | type[float]) -> int | float:
        try:
            return kind(value or 0)
        except (TypeError, ValueError):
            return kind()

    return {
        "input_type": input_type,
        "container": str(fmt.get("format_name") or ""),
        "audio_codec": str(audio.get("codec_name") or ""),
        "duration_seconds": number(fmt.get("duration"), float),
        "sample_rate": number(audio.get("sample_rate"), int),
        "channels": number(audio.get("channels"), int),
        "channel_layout": str(audio.get("channel_layout") or ""),
        "bit_rate": number(audio.get("bit_rate") or fmt.get("bit_rate"), int),
        "has_audio_stream": has_audio,
        "has_video_stream": has_video,
        "has_attached_picture": has_attached_picture,
    }


def require_decodable_audio(path: str | Path) -> dict[str, Any]:
    metadata = probe_media(path)
    if metadata["input_type"] == "invalid":
        raise ExternalToolError(f"Invalid or corrupt media: {metadata.get('error', 'unknown error')}")
    if not metadata.get("has_audio_stream"):
        raise ExternalToolError("Input media does not contain an audio stream.")
    return metadata
