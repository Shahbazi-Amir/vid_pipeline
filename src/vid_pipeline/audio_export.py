"""User-facing audio export from local or downloaded video sources.

This module is intentionally separate from :mod:`vid_pipeline.audio`, whose
16 kHz mono WAV output is a transcription/ASR intermediate.
"""

from __future__ import annotations

import json
import re
import shutil
import subprocess
import tempfile
import uuid
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from vid_pipeline.download import download_video
from vid_pipeline.errors import ExternalToolError

SUPPORTED_AUDIO_FORMATS = ("mp3", "wav", "m4a", "flac", "opus")
MP3_BITRATES = ("128k", "192k", "256k", "320k")
_DEFAULT_BITRATES = {"mp3": "192k", "m4a": "192k", "opus": "128k"}
_TRANSCODE_CODECS = {
    "mp3": "libmp3lame",
    "wav": "pcm_s16le",
    "m4a": "aac",
    "flac": "flac",
    "opus": "libopus",
}
_OUTPUT_CODECS = {
    "mp3": frozenset({"mp3"}),
    "wav": frozenset(
        {
            "pcm_s16le",
            "pcm_s24le",
            "pcm_s32le",
            "pcm_f32le",
            "pcm_f64le",
        }
    ),
    "m4a": frozenset({"aac", "alac"}),
    "flac": frozenset({"flac"}),
    "opus": frozenset({"opus"}),
}
_SAFE_NAME = re.compile(r"[^\w.-]+", re.UNICODE)


@dataclass(frozen=True, slots=True)
class AudioStreamInfo:
    """One audio stream and its deterministic audio-stream ordinal."""

    index: int
    ordinal: int
    codec: str
    sample_rate: int
    channels: int
    channel_layout: str
    is_default: bool


@dataclass(frozen=True, slots=True)
class VideoProbe:
    """Probe data required to export and validate delivery audio."""

    duration_seconds: float
    container: str
    audio_streams: tuple[AudioStreamInfo, ...]


@dataclass(frozen=True, slots=True)
class AudioExportResult:
    """Validated export result returned to callers and the CLI."""

    output: Path
    format: str
    codec: str
    method: str
    source_audio_stream: int
    channels: int
    sample_rate: int
    input_duration_seconds: float
    output_duration_seconds: float

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["output"] = str(self.output)
        return payload


def _require_tool(name: str) -> str:
    executable = shutil.which(name)
    if not executable:
        raise ExternalToolError(f"Required tool '{name}' was not found in PATH.")
    return executable


def _run(command: list[str], *, action: str) -> subprocess.CompletedProcess[str]:
    result = subprocess.run(command, capture_output=True, text=True, check=False)
    if result.returncode:
        diagnostic = (result.stderr or result.stdout).strip()
        if len(diagnostic) > 1200:
            diagnostic = diagnostic[-1200:]
        suffix = f" Details: {diagnostic}" if diagnostic else ""
        raise ExternalToolError(f"{action} failed.{suffix}")
    return result


def _integer(value: Any) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


def _number(value: Any) -> float:
    try:
        return float(value or 0)
    except (TypeError, ValueError):
        return 0.0


def probe_video(path: str | Path) -> VideoProbe:
    """Require a probeable motion-video source with at least one audio stream."""
    source = Path(path)
    if not source.exists():
        raise ExternalToolError(f"Video file does not exist: {source}")
    if not source.is_file():
        raise ExternalToolError(f"Video input is not a file: {source}")
    if source.stat().st_size <= 0:
        raise ExternalToolError(f"Invalid or corrupt video: file is empty: {source}")

    result = _run(
        [
            _require_tool("ffprobe"),
            "-v",
            "error",
            "-show_entries",
            (
                "format=format_name,duration:"
                "stream=index,codec_type,codec_name,sample_rate,channels,"
                "channel_layout,duration:stream_disposition=attached_pic,default"
            ),
            "-of",
            "json",
            str(source),
        ],
        action="FFprobe input validation",
    )
    try:
        raw = json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        raise ExternalToolError("FFprobe input validation returned invalid metadata.") from exc

    streams = raw.get("streams") or []
    motion_video = [
        stream
        for stream in streams
        if stream.get("codec_type") == "video"
        and _integer((stream.get("disposition") or {}).get("attached_pic")) != 1
    ]
    if not motion_video:
        raise ExternalToolError("Input is not a video with a motion-video stream.")

    audio: list[AudioStreamInfo] = []
    for stream in streams:
        if stream.get("codec_type") != "audio":
            continue
        disposition = stream.get("disposition") or {}
        audio.append(
            AudioStreamInfo(
                index=_integer(stream.get("index")),
                ordinal=len(audio),
                codec=str(stream.get("codec_name") or ""),
                sample_rate=_integer(stream.get("sample_rate")),
                channels=_integer(stream.get("channels")),
                channel_layout=str(stream.get("channel_layout") or ""),
                is_default=_integer(disposition.get("default")) == 1,
            )
        )
    if not audio:
        raise ExternalToolError("Video does not contain an audio stream.")

    fmt = raw.get("format") or {}
    duration = _number(fmt.get("duration"))
    if duration <= 0:
        duration = max((_number(stream.get("duration")) for stream in streams), default=0.0)
    return VideoProbe(
        duration_seconds=duration,
        container=str(fmt.get("format_name") or ""),
        audio_streams=tuple(audio),
    )


def _select_stream(probe: VideoProbe, requested: int | None) -> AudioStreamInfo:
    if requested is not None:
        if requested < 0 or requested >= len(probe.audio_streams):
            raise ValueError(
                f"audio stream must be between 0 and {len(probe.audio_streams) - 1}"
            )
        return probe.audio_streams[requested]
    return next((stream for stream in probe.audio_streams if stream.is_default), probe.audio_streams[0])


def _validate_options(format_name: str, bitrate: str | None) -> str:
    normalized = format_name.casefold().lstrip(".")
    if normalized not in SUPPORTED_AUDIO_FORMATS:
        raise ValueError(
            f"audio format must be one of: {', '.join(SUPPORTED_AUDIO_FORMATS)}"
        )
    if bitrate is not None:
        if normalized != "mp3":
            raise ValueError("--bitrate is supported only for MP3 output")
        if bitrate not in MP3_BITRATES:
            raise ValueError(f"MP3 bitrate must be one of: {', '.join(MP3_BITRATES)}")
    return normalized


def _can_stream_copy(stream: AudioStreamInfo, format_name: str, bitrate: str | None) -> bool:
    return bitrate is None and stream.codec in _OUTPUT_CODECS[format_name]


def _duration_is_plausible(source: float, output: float) -> bool:
    if output <= 0:
        return False
    if source <= 0:
        return True
    return abs(source - output) <= max(2.0, source * 0.05)


def _probe_audio_output(path: Path) -> dict[str, Any]:
    result = _run(
        [
            _require_tool("ffprobe"),
            "-v",
            "error",
            "-show_entries",
            "format=duration:stream=codec_type,codec_name,sample_rate,channels",
            "-of",
            "json",
            str(path),
        ],
        action="FFprobe output validation",
    )
    try:
        return json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        raise ExternalToolError("FFprobe output validation returned invalid metadata.") from exc


def _validate_output(
    path: Path,
    *,
    format_name: str,
    source_probe: VideoProbe,
    source_stream: AudioStreamInfo,
) -> tuple[str, int, int, float]:
    if not path.is_file() or path.stat().st_size <= 0:
        raise ExternalToolError("Audio export did not create a non-empty output file.")
    metadata = _probe_audio_output(path)
    streams = metadata.get("streams") or []
    audio = [stream for stream in streams if stream.get("codec_type") == "audio"]
    if len(audio) != 1:
        raise ExternalToolError("Exported file must contain exactly one audio stream.")
    if any(stream.get("codec_type") == "video" for stream in streams):
        raise ExternalToolError("Exported audio unexpectedly contains a video stream.")
    stream = audio[0]
    codec = str(stream.get("codec_name") or "")
    if codec not in _OUTPUT_CODECS[format_name]:
        raise ExternalToolError(
            f"Exported codec '{codec or 'unknown'}' is incompatible with {format_name}."
        )
    channels = _integer(stream.get("channels"))
    if source_stream.channels and channels != source_stream.channels:
        raise ExternalToolError("Exported audio channel count differs unexpectedly from the source.")
    sample_rate = _integer(stream.get("sample_rate"))
    output_duration = _number((metadata.get("format") or {}).get("duration"))
    if not _duration_is_plausible(source_probe.duration_seconds, output_duration):
        raise ExternalToolError("Exported audio duration differs unexpectedly from the input video.")

    _run(
        [
            _require_tool("ffmpeg"),
            "-hide_banner",
            "-loglevel",
            "error",
            "-nostdin",
            "-i",
            str(path),
            "-map",
            "0:a:0",
            "-f",
            "null",
            "-",
        ],
        action="Audio decode validation",
    )
    return codec, channels, sample_rate, output_duration


def export_audio(
    source: str | Path,
    destination: str | Path,
    *,
    format_name: str,
    bitrate: str | None = None,
    audio_stream: int | None = None,
    overwrite: bool = False,
) -> AudioExportResult:
    """Export one selected audio stream from a validated local video."""
    normalized_format = _validate_options(format_name, bitrate)
    source_path = Path(source).resolve()
    target = Path(destination).resolve()
    if target.suffix.casefold() != f".{normalized_format}":
        raise ValueError(f"output path must end with .{normalized_format}")
    if source_path == target:
        raise ValueError("output path must not overwrite the input video")
    if target.exists() and not overwrite:
        raise ExternalToolError(f"Output already exists: {target}. Use --overwrite to replace it.")

    source_probe = probe_video(source_path)
    selected = _select_stream(source_probe, audio_stream)
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = target.with_name(
        f".{target.stem}.{uuid.uuid4().hex}.tmp.{normalized_format}"
    )
    method = "copy" if _can_stream_copy(selected, normalized_format, bitrate) else "transcode"
    command = [
        _require_tool("ffmpeg"),
        "-hide_banner",
        "-loglevel",
        "error",
        "-nostdin",
        "-y",
        "-i",
        str(source_path),
        "-map",
        f"0:a:{selected.ordinal}",
        "-vn",
        "-sn",
        "-dn",
        "-map_metadata",
        "0",
    ]
    if method == "copy":
        command.extend(["-c:a", "copy"])
    else:
        command.extend(["-c:a", _TRANSCODE_CODECS[normalized_format]])
        selected_bitrate = bitrate or _DEFAULT_BITRATES.get(normalized_format)
        if selected_bitrate:
            command.extend(["-b:a", selected_bitrate])
    command.append(str(temporary))

    try:
        _run(command, action="Audio export")
        codec, channels, sample_rate, output_duration = _validate_output(
            temporary,
            format_name=normalized_format,
            source_probe=source_probe,
            source_stream=selected,
        )
        temporary.replace(target)
    except Exception:
        temporary.unlink(missing_ok=True)
        raise

    return AudioExportResult(
        output=target,
        format=normalized_format,
        codec=codec,
        method=method,
        source_audio_stream=selected.ordinal,
        channels=channels,
        sample_rate=sample_rate,
        input_duration_seconds=source_probe.duration_seconds,
        output_duration_seconds=output_duration,
    )


def _is_http_url(value: str) -> bool:
    parsed = urlparse(value)
    return parsed.scheme.casefold() in {"http", "https"} and bool(parsed.netloc)


def _default_url_stem(metadata: dict[str, Any], downloaded: Path) -> str:
    raw = str(metadata.get("title") or metadata.get("id") or downloaded.stem).strip()
    cleaned = _SAFE_NAME.sub("-", raw).strip("-._")
    return (cleaned or "video")[:120]


def extract_audio(
    input_value: str | Path,
    *,
    format_name: str,
    output: str | Path | None = None,
    bitrate: str | None = None,
    audio_stream: int | None = None,
    overwrite: bool = False,
) -> AudioExportResult:
    """Resolve a local path or HTTP(S) URL and export delivery audio."""
    normalized_format = _validate_options(format_name, bitrate)
    raw = str(input_value)
    parsed = urlparse(raw)
    if parsed.scheme and "://" in raw and not _is_http_url(raw):
        raise ValueError("video URL must use http:// or https:// and include a host")

    if _is_http_url(raw):
        with tempfile.TemporaryDirectory(prefix="vid-pipeline-audio-") as temporary_root:
            download_root = Path(temporary_root) / "download"
            try:
                downloaded, metadata = download_video(raw, download_root)
            except ExternalToolError:
                raise
            except Exception as exc:
                raise ExternalToolError(f"Video download failed: {exc}") from exc
            destination = (
                Path(output)
                if output is not None
                else Path.cwd() / f"{_default_url_stem(metadata, downloaded)}.{normalized_format}"
            )
            return export_audio(
                downloaded,
                destination,
                format_name=normalized_format,
                bitrate=bitrate,
                audio_stream=audio_stream,
                overwrite=overwrite,
            )

    source = Path(input_value)
    destination = Path(output) if output is not None else source.with_suffix(f".{normalized_format}")
    return export_audio(
        source,
        destination,
        format_name=normalized_format,
        bitrate=bitrate,
        audio_stream=audio_stream,
        overwrite=overwrite,
    )
