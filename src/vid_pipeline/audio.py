"""Audio extraction, normalization, and probing with FFmpeg."""

from __future__ import annotations

import json
import shutil
import subprocess
import uuid
from pathlib import Path
from typing import Any

from vid_pipeline.errors import ExternalToolError
from vid_pipeline.media import probe_media as inspect_media
from vid_pipeline.media import require_decodable_audio

AUDIO_PROFILES = ("none", "safe", "noisy")
PROFILE_FILTERS = {
    "none": [],
    "safe": ["highpass=f=60", "lowpass=f=7800", "loudnorm=I=-20:LRA=11:TP=-2"],
    "noisy": ["highpass=f=100", "lowpass=f=7000", "afftdn=nf=-25", "loudnorm=I=-20:LRA=9:TP=-2"],
}


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


def normalize_audio(
    media_path: str | Path,
    output_path: str | Path,
    overwrite: bool = False,
    profile: str = "safe",
    quality_path: str | Path | None = None,
) -> Path:
    ffmpeg = require_tool("ffmpeg")
    if profile not in AUDIO_PROFILES:
        raise ValueError(f"audio profile must be one of: {', '.join(AUDIO_PROFILES)}")
    source = Path(media_path)
    destination = Path(output_path)
    if not source.exists():
        raise ExternalToolError(f"Media file does not exist: {source}")
    source_probe = require_decodable_audio(source)
    destination.parent.mkdir(parents=True, exist_ok=True)
    if destination.exists() and not overwrite:
        validate_normalized_audio(destination)
        return destination
    temporary = destination.with_name(f".{destination.stem}.{uuid.uuid4().hex}.tmp.wav")
    command = [
        ffmpeg,
        "-hide_banner",
        "-loglevel",
        "error",
        "-y",
        "-i",
        str(source),
        "-vn",
        "-ac",
        "1",
        "-ar",
        "16000",
    ]
    filters = PROFILE_FILTERS[profile]
    if filters:
        command.extend(["-af", ",".join(filters)])
    command.extend([
        "-c:a",
        "pcm_s16le",
        str(temporary),
    ])
    try:
        run_command(command)
        normalized = validate_normalized_audio(temporary)
        source_duration = float(source_probe.get("duration_seconds") or 0)
        output_duration = float((normalized.get("format") or {}).get("duration") or 0)
        if source_duration and (output_duration <= 0 or abs(output_duration - source_duration) > max(2, source_duration * .05)):
            raise ExternalToolError("Normalized audio duration differs unexpectedly from input media.")
        temporary.replace(destination)
        report_path = Path(quality_path) if quality_path else destination.parent / "audio-quality.json"
        report = analyze_audio_quality(destination, source_probe, profile, filters)
        temp_report = report_path.with_name(f".{report_path.name}.{uuid.uuid4().hex}.tmp")
        temp_report.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
        temp_report.replace(report_path)
    except Exception:
        temporary.unlink(missing_ok=True)
        raise
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


def analyze_audio_quality(
    path: Path, source: dict[str, Any], profile: str, filters: list[str]
) -> dict[str, Any]:
    ffmpeg = require_tool("ffmpeg")
    result = subprocess.run(
        [ffmpeg, "-hide_banner", "-nostats", "-i", str(path), "-af",
         "volumedetect,silencedetect=n=-50dB:d=0.25", "-f", "null", "-"],
        capture_output=True, text=True, check=False,
    )
    text = result.stderr
    def metric(name: str) -> float | None:
        import re
        match = re.search(rf"{name}:\s*(-?(?:inf|\d+(?:\.\d+)?))\s*dB", text)
        if not match or match.group(1) == "-inf":
            return None
        return float(match.group(1))
    peak = metric("max_volume")
    mean = metric("mean_volume")
    import re
    silences = [float(v) for v in re.findall(r"silence_duration:\s*(\d+(?:\.\d+)?)", text)]
    duration = float(inspect_media(path).get("duration_seconds") or 0)
    ratio = min(1.0, sum(silences) / duration) if duration else 0.0
    warnings: list[str] = []
    clipping = peak is not None and peak >= -0.1
    low = mean is None or mean < -40
    if clipping:
        warnings.append("possible_clipping")
    if low:
        warnings.append("very_low_volume")
    if ratio > .8:
        warnings.append("mostly_silence")
    noise_probability = min(1.0, max(0.0, (ratio - .15) * .5))
    return {
        "schema_version": 1, "input_type": source.get("input_type", "unknown"),
        "duration_seconds": duration, "sample_rate": 16000, "channels": 1,
        "codec": "pcm_s16le", "peak_dbfs": peak, "mean_volume_db": mean,
        "clipping_detected": clipping, "silence_ratio": ratio,
        "very_low_volume": low, "noise_probability": noise_probability,
        "preprocessing_profile": profile, "filters_applied": list(filters),
        "warnings": warnings,
    }


def validate_normalized_audio(path: str | Path) -> dict[str, Any]:
    data = probe_media(path)
    audio_streams = [
        item for item in data.get("streams", []) if item.get("codec_type") == "audio"
    ]
    if len(audio_streams) != 1:
        raise ExternalToolError("Normalized file must contain exactly one audio stream.")
    stream = audio_streams[0]
    if stream.get("codec_name") != "pcm_s16le":
        raise ExternalToolError("Normalized audio must use pcm_s16le.")
    if int(stream.get("sample_rate", 0)) != 16000 or int(stream.get("channels", 0)) != 1:
        raise ExternalToolError("Normalized audio must be mono and 16kHz.")
    return data
