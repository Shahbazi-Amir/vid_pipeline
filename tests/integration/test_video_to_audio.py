"""Real FFmpeg end-to-end coverage for delivery audio export."""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest

from vid_pipeline.audio_export import export_audio, extract_audio, probe_video
from vid_pipeline.cli import build_parser
from vid_pipeline.errors import ExternalToolError
from vid_pipeline.media import probe_media

pytestmark = pytest.mark.skipif(
    not shutil.which("ffmpeg") or not shutil.which("ffprobe"),
    reason="FFmpeg/FFprobe unavailable",
)


def ffmpeg(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [
            shutil.which("ffmpeg") or "ffmpeg",
            "-hide_banner",
            "-loglevel",
            "error",
            "-y",
            *args,
        ],
        capture_output=True,
        text=True,
        check=False,
    )


def make_video(
    path: Path,
    *,
    sample_rate: int = 44100,
    channels: int = 2,
    audio_codec: str = "aac",
    video_codec: str = "mpeg4",
) -> None:
    result = ffmpeg(
        "-f",
        "lavfi",
        "-i",
        "testsrc=size=64x64:rate=10:duration=1",
        "-f",
        "lavfi",
        "-i",
        f"sine=frequency=440:duration=1:sample_rate={sample_rate}",
        "-shortest",
        "-c:v",
        video_codec,
        "-pix_fmt",
        "yuv420p",
        "-c:a",
        audio_codec,
        "-ac",
        str(channels),
        str(path),
    )
    if result.returncode:
        pytest.skip(f"fixture codec unavailable: {result.stderr.strip()[-300:]}")


@pytest.mark.parametrize(
    "format_name,expected_codec,expected_method",
    [
        ("mp3", "mp3", "transcode"),
        ("wav", "pcm_s16le", "transcode"),
        ("m4a", "aac", "copy"),
    ],
)
def test_mp4_aac_exports_delivery_formats(
    tmp_path: Path, format_name: str, expected_codec: str, expected_method: str
) -> None:
    source = tmp_path / "input video.mp4"
    make_video(source)

    result = extract_audio(source, format_name=format_name)
    metadata = probe_media(result.output)

    assert result.output == tmp_path / f"input video.{format_name}"
    assert result.codec == expected_codec
    assert result.method == expected_method
    assert result.channels == 2
    assert 0.9 <= result.output_duration_seconds <= 1.2
    assert metadata["audio_codec"] == expected_codec
    assert metadata["has_video_stream"] is False


def test_mkv_exports_flac_without_lossy_intermediate(tmp_path: Path) -> None:
    source = tmp_path / "source.mkv"
    make_video(source, sample_rate=48000)

    result = extract_audio(source, format_name="flac", output=tmp_path / "custom.flac")

    assert result.codec == "flac"
    assert result.method == "transcode"
    assert result.sample_rate == 48000
    assert result.output == tmp_path / "custom.flac"


def test_webm_opus_uses_safe_stream_copy(tmp_path: Path) -> None:
    source = tmp_path / "source.webm"
    make_video(source, sample_rate=48000, audio_codec="libopus", video_codec="libvpx-vp9")

    result = extract_audio(source, format_name="opus")

    assert result.codec == "opus"
    assert result.method == "copy"
    assert result.channels == 2


def test_stereo_and_source_sample_rate_are_preserved_by_default(tmp_path: Path) -> None:
    source = tmp_path / "stereo-44100.mp4"
    make_video(source, sample_rate=44100, channels=2)

    result = extract_audio(source, format_name="wav")

    assert result.channels == 2
    assert result.sample_rate == 44100


def test_mp3_bitrate_option_is_applied(tmp_path: Path) -> None:
    source = tmp_path / "bitrate.mp4"
    make_video(source)

    result = extract_audio(source, format_name="mp3", bitrate="192k")
    bit_rate = int(probe_media(result.output)["bit_rate"])

    assert result.method == "transcode"
    assert 170_000 <= bit_rate <= 215_000


def test_default_stream_is_deterministic_and_explicit_selection_works(tmp_path: Path) -> None:
    source = tmp_path / "multi.mkv"
    result = ffmpeg(
        "-f",
        "lavfi",
        "-i",
        "testsrc=size=64x64:rate=10:duration=1",
        "-f",
        "lavfi",
        "-i",
        "sine=frequency=330:duration=1:sample_rate=48000",
        "-f",
        "lavfi",
        "-i",
        "sine=frequency=660:duration=1:sample_rate=48000",
        "-map",
        "0:v",
        "-map",
        "1:a",
        "-map",
        "2:a",
        "-c:v",
        "mpeg4",
        "-c:a",
        "aac",
        "-disposition:a:0",
        "0",
        "-disposition:a:1",
        "default",
        str(source),
    )
    assert result.returncode == 0, result.stderr

    default_result = export_audio(
        source, tmp_path / "default.flac", format_name="flac"
    )
    explicit_result = export_audio(
        source, tmp_path / "first.flac", format_name="flac", audio_stream=0
    )

    assert default_result.source_audio_stream == 1
    assert explicit_result.source_audio_stream == 0


def test_video_without_audio_fails_clearly(tmp_path: Path) -> None:
    source = tmp_path / "silent.mp4"
    result = ffmpeg(
        "-f",
        "lavfi",
        "-i",
        "color=c=black:s=64x64:d=1",
        "-an",
        "-c:v",
        "mpeg4",
        str(source),
    )
    assert result.returncode == 0, result.stderr

    with pytest.raises(ExternalToolError, match="does not contain an audio stream"):
        extract_audio(source, format_name="mp3")


def test_corrupt_and_audio_only_inputs_are_rejected(tmp_path: Path) -> None:
    corrupt = tmp_path / "corrupt.mp4"
    corrupt.write_bytes(b"not a video")
    with pytest.raises(ExternalToolError, match="FFprobe input validation"):
        extract_audio(corrupt, format_name="wav")

    audio = tmp_path / "audio.wav"
    result = ffmpeg(
        "-f", "lavfi", "-i", "sine=frequency=440:duration=1", str(audio)
    )
    assert result.returncode == 0, result.stderr
    with pytest.raises(ExternalToolError, match="not a video"):
        extract_audio(audio, format_name="wav", output=tmp_path / "audio-out.wav")


def test_overwrite_protection_and_explicit_overwrite(tmp_path: Path) -> None:
    source = tmp_path / "overwrite.mp4"
    make_video(source)
    output = tmp_path / "existing.mp3"
    output.write_bytes(b"keep me")

    with pytest.raises(ExternalToolError, match="Output already exists"):
        extract_audio(source, format_name="mp3", output=output)
    assert output.read_bytes() == b"keep me"

    result = extract_audio(source, format_name="mp3", output=output, overwrite=True)
    assert result.output == output
    assert output.stat().st_size > len(b"keep me")


def test_invalid_format_bitrate_output_and_stream_are_rejected(tmp_path: Path) -> None:
    source = tmp_path / "validation.mp4"
    make_video(source)

    with pytest.raises(ValueError, match="audio format"):
        extract_audio(source, format_name="wma")
    with pytest.raises(ValueError, match="bitrate is supported only"):
        extract_audio(source, format_name="wav", bitrate="192k")
    with pytest.raises(ValueError, match="must end with .mp3"):
        extract_audio(source, format_name="mp3", output=tmp_path / "wrong.wav")
    with pytest.raises(ValueError, match="audio stream must be"):
        extract_audio(source, format_name="flac", audio_stream=3)


def test_url_source_reuses_downloader_and_cleans_temporary_media(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    source = tmp_path / "controlled-source.mp4"
    make_video(source)
    download_directories: list[Path] = []

    def fake_download(url: str, output_dir: str | Path) -> tuple[Path, dict[str, str]]:
        assert url == "https://example.test/watch/123"
        destination = Path(output_dir)
        destination.mkdir(parents=True)
        downloaded = destination / "video.mp4"
        shutil.copy2(source, downloaded)
        download_directories.append(destination)
        return downloaded, {"title": "URL sample"}

    monkeypatch.setattr("vid_pipeline.audio_export.download_video", fake_download)
    monkeypatch.chdir(tmp_path)

    result = extract_audio("https://example.test/watch/123", format_name="mp3")

    assert result.output == tmp_path / "URL-sample.mp3"
    assert result.output.is_file()
    assert download_directories and not download_directories[0].exists()


def test_invalid_url_and_missing_input_fail_actionably(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="must use http"):
        extract_audio("ftp://example.test/video.mp4", format_name="mp3")
    with pytest.raises(ExternalToolError, match="does not exist"):
        extract_audio(tmp_path / "missing.mp4", format_name="mp3")


def test_cli_contract() -> None:
    args = build_parser().parse_args(
        [
            "extract-audio",
            "video.mp4",
            "--format",
            "mp3",
            "--bitrate",
            "320k",
            "--audio-stream",
            "1",
            "--output",
            "delivery.mp3",
            "--overwrite",
        ]
    )
    assert args.command == "extract-audio"
    assert args.format == "mp3"
    assert args.bitrate == "320k"
    assert args.audio_stream == 1
    assert args.output == Path("delivery.mp3")
    assert args.overwrite is True


def test_probe_reports_audio_streams(tmp_path: Path) -> None:
    source = tmp_path / "probe.mp4"
    make_video(source)
    probe = probe_video(source)
    assert probe.audio_streams[0].codec == "aac"
    assert probe.audio_streams[0].channels == 2
    assert probe.duration_seconds > 0
