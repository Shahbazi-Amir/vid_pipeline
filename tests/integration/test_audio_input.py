"""Real FFmpeg coverage for audio input handling."""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest

from vid_pipeline.audio import normalize_audio, validate_normalized_audio
from vid_pipeline.cli import build_parser
from vid_pipeline.errors import ExternalToolError
from vid_pipeline.media import (
    AUDIO_EXTENSIONS,
    discover_media,
    probe_media,
    require_decodable_audio,
)

pytestmark = pytest.mark.skipif(
    not shutil.which("ffmpeg") or not shutil.which("ffprobe"),
    reason="FFmpeg/FFprobe unavailable",
)

FORMATS = {
    "wav": ("pcm_s16le", []),
    "mp3": ("libmp3lame", []),
    "m4a": ("aac", ["-f", "ipod"]),
    "aac": ("aac", ["-f", "adts"]),
    "flac": ("flac", []),
    "ogg": ("libvorbis", []),
    "opus": ("libopus", ["-f", "opus"]),
    "webm": ("libopus", ["-f", "webm"]),
    "wma": ("wmav2", []),
    "aiff": ("pcm_s16be", []),
    "alac": ("alac", ["-f", "ipod"]),
    "caf": ("pcm_s16le", ["-f", "caf"]),
    "ac3": ("ac3", []),
    "amr": ("libopencore_amrnb", ["-ar", "8000", "-ac", "1", "-f", "amr"]),
}


def ffmpeg(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [shutil.which("ffmpeg") or "ffmpeg", "-hide_banner", "-loglevel", "error", "-y", *args],
        capture_output=True, text=True, check=False,
    )


def tone(path: Path, *, rate: int = 44100, channels: int = 2, volume: float = 0.2) -> None:
    result = ffmpeg(
        "-f", "lavfi", "-i", f"sine=frequency=440:duration=1:sample_rate={rate}",
        "-filter:a", f"volume={volume}", "-ac", str(channels), str(path),
    )
    assert result.returncode == 0, result.stderr


@pytest.mark.parametrize("extension,settings", FORMATS.items())
def test_real_audio_formats_normalize(
    tmp_path: Path, extension: str, settings: tuple[str, list[str]]
) -> None:
    codec, extra = settings
    target = tmp_path / f"input.{extension}"
    result = ffmpeg(
        "-f", "lavfi", "-i", "sine=frequency=440:duration=1:sample_rate=48000",
        "-ac", "2", "-c:a", codec, *extra, str(target),
    )
    if result.returncode:
        pytest.skip(f"encoder unavailable: {codec}: {result.stderr.strip()[-200:]}")
    assert probe_media(target)["input_type"] == "audio"
    output = tmp_path / f"normalized-{extension}.wav"
    normalize_audio(target, output, overwrite=True, profile="safe")
    stream = validate_normalized_audio(output)["streams"][0]
    assert stream["codec_name"] == "pcm_s16le"
    assert int(stream["sample_rate"]) == 16000
    assert int(stream["channels"]) == 1
    assert 0.9 <= float(probe_media(output)["duration_seconds"]) <= 1.1


@pytest.mark.parametrize("profile", ["none", "safe", "noisy"])
@pytest.mark.parametrize("rate", [44100, 48000])
def test_profiles_rates_and_stereo(tmp_path: Path, profile: str, rate: int) -> None:
    source = tmp_path / f"{profile}-{rate}.wav"
    tone(source, rate=rate)
    output = tmp_path / f"out-{profile}-{rate}.wav"
    normalize_audio(source, output, overwrite=True, profile=profile)
    report = json.loads((tmp_path / "audio-quality.json").read_text())
    assert report["preprocessing_profile"] == profile
    assert report["codec"] == "pcm_s16le"
    assert report["sample_rate"] == 16000
    assert report["channels"] == 1


def test_probe_ignores_extension_and_rejects_invalid_media(tmp_path: Path) -> None:
    encoded = tmp_path / "encoded.wav"
    tone(encoded)
    source = tmp_path / "wrong.bin"
    encoded.replace(source)
    assert probe_media(source)["input_type"] == "audio"
    empty = tmp_path / "empty.mp3"
    empty.touch()
    corrupt = tmp_path / "corrupt.wav"
    corrupt.write_bytes(b"not audio")
    assert probe_media(empty)["input_type"] == "invalid"
    assert probe_media(corrupt)["input_type"] == "invalid"
    with pytest.raises(ExternalToolError, match="Invalid or corrupt"):
        require_decodable_audio(corrupt)


def test_audio_with_attached_cover_art_stays_audio(tmp_path: Path) -> None:
    source = tmp_path / "covered.mp3"
    result = ffmpeg(
        "-f", "lavfi", "-i", "sine=frequency=440:duration=1:sample_rate=44100",
        "-f", "lavfi", "-i", "color=c=blue:s=32x32:d=1",
        "-map", "0:a", "-map", "1:v", "-c:a", "libmp3lame", "-c:v", "mjpeg",
        "-frames:v", "1", "-disposition:v:0", "attached_pic", str(source),
    )
    if result.returncode:
        pytest.skip(f"cover-art encoder unavailable: {result.stderr.strip()[-200:]}")
    metadata = probe_media(source)
    assert metadata["input_type"] == "audio"
    assert metadata["has_audio_stream"] is True
    assert metadata["has_video_stream"] is False
    assert metadata["has_attached_picture"] is True
    output = tmp_path / "covered-out.wav"
    normalize_audio(source, output, overwrite=True, profile="safe")
    validate_normalized_audio(output)


def test_video_without_audio_is_rejected(tmp_path: Path) -> None:
    source = tmp_path / "silent-video.mp4"
    result = ffmpeg(
        "-f", "lavfi", "-i", "color=c=black:s=160x120:d=1", "-an", str(source)
    )
    assert result.returncode == 0, result.stderr
    assert probe_media(source)["input_type"] == "video"
    with pytest.raises(ExternalToolError, match="does not contain an audio stream"):
        normalize_audio(source, tmp_path / "out.wav", overwrite=True)


def test_video_with_audio_regression(tmp_path: Path) -> None:
    source = tmp_path / "video.mp4"
    result = ffmpeg(
        "-f", "lavfi", "-i", "color=c=black:s=160x120:d=1",
        "-f", "lavfi", "-i", "sine=frequency=440:duration=1",
        "-shortest", "-c:v", "mpeg4", "-c:a", "aac", str(source),
    )
    assert result.returncode == 0, result.stderr
    assert probe_media(source)["input_type"] == "video"
    output = tmp_path / "video-out.wav"
    normalize_audio(source, output, overwrite=True, profile="safe")
    validate_normalized_audio(output)


def test_mixed_folder_discovery_and_validation(tmp_path: Path) -> None:
    audio = tmp_path / "speech.wav"
    tone(audio)
    video = tmp_path / "interview.mp4"
    result = ffmpeg(
        "-f", "lavfi", "-i", "color=c=black:s=160x120:d=1",
        "-f", "lavfi", "-i", "sine=frequency=330:duration=1",
        "-shortest", "-c:v", "mpeg4", "-c:a", "aac", str(video),
    )
    assert result.returncode == 0, result.stderr
    invalid = tmp_path / "broken.mp3"
    invalid.write_bytes(b"corrupt")
    discovered = discover_media(tmp_path)
    assert discovered == sorted([invalid, video, audio])
    assert probe_media(audio)["input_type"] == "audio"
    assert probe_media(video)["input_type"] == "video"
    assert probe_media(invalid)["input_type"] == "invalid"


def test_low_volume_clipping_noise_and_silence_reports(tmp_path: Path) -> None:
    for name, source_filter in {
        "low": "sine=frequency=440:duration=1,volume=0.001",
        "clipped": "sine=frequency=440:duration=1,volume=10",
        "noise": "anoisesrc=d=1:c=pink:a=0.2",
        "silence": "anullsrc=r=48000:cl=stereo:d=1",
    }.items():
        source = tmp_path / f"{name}.wav"
        result = ffmpeg("-f", "lavfi", "-i", source_filter, str(source))
        assert result.returncode == 0, result.stderr
        output = tmp_path / f"{name}-out.wav"
        report_path = tmp_path / f"{name}.json"
        normalize_audio(source, output, overwrite=True, quality_path=report_path)
        report = json.loads(report_path.read_text())
        assert 0 <= report["silence_ratio"] <= 1
        assert isinstance(report["warnings"], list)


def test_registry_contains_required_extensions() -> None:
    assert {
        ".wav", ".mp3", ".m4a", ".aac", ".flac", ".ogg", ".opus", ".webm",
        ".wma", ".aiff", ".aif", ".alac", ".caf", ".ac3", ".amr",
    } <= AUDIO_EXTENSIONS


@pytest.mark.parametrize(
    "command,argument",
    [
        ("run-file", "speech.wav"), ("run-folder", "media"),
        ("submit-file", "speech.wav"), ("submit-folder", "media"),
        ("github-submit-file", "speech.wav"), ("github-submit-folder", "media"),
        ("run-url", "https://example.com/speech.mp3"),
        ("github-run-url", "https://example.com/speech.mp3"),
    ],
)
def test_audio_profile_cli_contract(command: str, argument: str) -> None:
    args = build_parser().parse_args([command, argument, "--audio-profile", "noisy"])
    assert args.audio_profile == "noisy"
