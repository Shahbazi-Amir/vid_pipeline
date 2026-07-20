"""Audio extraction, normalization, and probing with FFmpeg."""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path
from typing import Any

from vid_pipeline.errors import ExternalToolError


def require_tool(name: str) -> str:
    executable = shutil.which(name)
    if not executable:
        raise ExternalToolError(f"Required tool '{name}' was not found in PATH.")
    return executable


def run_command(command: list[str]) -> subprocess.CompletedProcess[str]:
    result = subprocess.run(command, capture_output=True, text=True, check=False)
    if result.returncode != 0:
        message = result.stderr.strip() or result.stdout.strip() or "unknown error"
        raise ExternalToolError(f"Command failed ({command[0]}): {message}")
    return result


def normalize_audio(video_path: str | Path, output_path: str | Path, overwrite: bool = False) -> Path:
    ffmpeg = require_tool("ffmpeg")
    source = Path(video_path)
    destination = Path(output_path)
    if not source.exists():
        raise ExternalToolError(f"Video file does not exist: {source}")
    destination.parent.mkdir(parents=True, exist_ok=True)
    if destination.exists() and not overwrite:
        validate_normalized_audio(destination)
        return destination
    command = [
        ffmpeg,
        "-hide_banner",
        "-loglevel",
        "error",
        "-y" if overwrite else "-n",
        "-i",
        str(source),
        "-vn",
        "-ac",
        "1",
        "-ar",
        "16000",
        "-c:a",
        "pcm_s16le",
        str(destination),
    ]
    run_command(command)
    if not destination.exists() or destination.stat().st_size == 0:
        raise ExternalToolError("FFmpeg did not create a valid audio file.")
    return destination


def probe_media(path: str | Path) -> dict[str, Any]:
    ffprobe = require_tool("ffprobe")
    result = run_command(
        [
            ffprobe,
            "-v",
            "error",
            "-show_entries",
            "format=duration:stream=codec_type,codec_name,sample_rate,channels",
            "-of",
            "json",
            str(path),
        ]
    )
    return json.loads(result.stdout)


def validate_normalized_audio(path: str | Path) -> dict[str, Any]:
    data = probe_media(path)
    audio_streams = [
        item for item in data.get("streams", []) if item.get("codec_type") == "audio"
    ]
    if len(audio_streams) != 1:
        raise ExternalToolError("Normalized file must contain exactly one audio stream.")
    stream = audio_streams[0]
    if int(stream.get("sample_rate", 0)) != 16000 or int(stream.get("channels", 0)) != 1:
        raise ExternalToolError("Normalized audio must be mono and 16kHz.")
    return data
