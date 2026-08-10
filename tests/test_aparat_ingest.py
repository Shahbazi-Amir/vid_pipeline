from __future__ import annotations

import hashlib
import io
import json
import urllib.error
from pathlib import Path

import pytest

from vid_pipeline import aparat
from vid_pipeline.aparat import (
    AparatPermanentError,
    AparatTransientError,
    ResolvedAparatMedia,
    download_verified_media,
    ensure_verified_aparat_media,
    resolve_aparat_media,
)


def _payload(*, direct: str = "https://cdn.asset.aparat.com/video.mp4?secret=never-log"):
    return {
        "video": {
            "uid": "2ptDl",
            "title": "episode two",
            "duration": 1395,
            "process": "done",
            "file_link_all": [
                {"profile": "144p", "urls": [direct.replace("video", "video-144")]},
                {"profile": "360p", "urls": [direct]},
                {"profile": "720p", "urls": [direct.replace("video", "video-720")]},
            ],
        }
    }


def test_supported_aparat_api_schema_selects_audio_efficient_profile() -> None:
    resolved = resolve_aparat_media(
        "https://www.aparat.com/v/2ptDl",
        expected_uid="2ptDl",
        request_json=lambda _url, _timeout: _payload(),
    )
    assert resolved.profile == "360p"
    assert resolved.duration_seconds == 1395
    assert "never-log" not in repr(resolved)


@pytest.mark.parametrize(
    "payload",
    [
        {},
        {"video": {"uid": "wrong", "duration": 1, "file_link_all": []}},
        {"video": {"uid": "2ptDl", "duration": 1}},
        {"video": {"uid": "2ptDl", "duration": 1, "file_link_all": []}},
    ],
)
def test_invalid_schema_is_permanent_and_fail_fast(payload) -> None:
    calls = 0

    def request(_url: str, _timeout: float):
        nonlocal calls
        calls += 1
        return payload

    with pytest.raises(AparatPermanentError):
        resolve_aparat_media("https://www.aparat.com/v/2ptDl", request_json=request)
    assert calls == 1


def test_transient_api_failure_retries_with_bounded_backoff() -> None:
    calls = 0
    sleeps = []

    def request(url: str, _timeout: float):
        nonlocal calls
        calls += 1
        if calls == 1:
            raise urllib.error.HTTPError(url, 503, "busy", {}, None)
        return _payload()

    resolved = resolve_aparat_media(
        "https://www.aparat.com/v/2ptDl",
        request_json=request,
        sleep=sleeps.append,
    )
    assert resolved.uid == "2ptDl"
    assert calls == 2
    assert sleeps == [1.0]


def test_direct_signed_url_never_appears_in_output(capsys) -> None:
    resolved = resolve_aparat_media(
        "https://www.aparat.com/v/2ptDl",
        request_json=lambda _url, _timeout: _payload(),
    )
    print(resolved)
    captured = capsys.readouterr()
    assert "secret=" not in captured.out + captured.err


class _Response(io.BytesIO):
    def __init__(self, value: bytes, declared: int | None = None) -> None:
        super().__init__(value)
        self.headers = {"Content-Length": str(declared if declared is not None else len(value))}


def _resolved() -> ResolvedAparatMedia:
    return ResolvedAparatMedia(
        source_url="https://www.aparat.com/v/2ptDl",
        uid="2ptDl",
        title="episode two",
        duration_seconds=1395,
        profile="360p",
        resolver_type="test",
        direct_url="https://cdn.asset.aparat.com/video.mp4?secret=never-log",
    )


def test_download_uses_part_verifies_and_atomically_finalizes(tmp_path: Path, monkeypatch) -> None:
    destination = tmp_path / "media.mp4"
    content = b"verified-media"

    def probe(path: Path):
        assert path.name.endswith(".part")
        assert not destination.exists()
        return {
            "duration_seconds": 10.0,
            "container": "mp4",
            "audio_codec": "aac",
            "video_codec": "h264",
        }, 0.1

    monkeypatch.setattr(aparat, "_probe_summary", probe)
    result = download_verified_media(
        _resolved(),
        destination,
        open_media=lambda _url, _timeout: _Response(content),
    )
    assert destination.read_bytes() == content
    assert not (tmp_path / "media.mp4.part").exists()
    assert result["media_size_bytes"] == len(content)
    assert result["media_sha256"] == hashlib.sha256(content).hexdigest()


def test_incomplete_download_is_never_finalized(tmp_path: Path) -> None:
    destination = tmp_path / "media.mp4"
    with pytest.raises(AparatTransientError):
        download_verified_media(
            _resolved(),
            destination,
            attempts=1,
            open_media=lambda _url, _timeout: _Response(b"abc", declared=10),
        )
    assert not destination.exists()
    assert not (tmp_path / "media.mp4.part").exists()


def test_verified_media_is_reused_without_resolve_or_redownload(tmp_path: Path, monkeypatch) -> None:
    destination = tmp_path / "media.mp4"
    content = b"already-verified"
    destination.write_bytes(content)
    metadata = {
        "source_url": "https://www.aparat.com/v/2ptDl",
        "media_size_bytes": len(content),
        "media_sha256": hashlib.sha256(content).hexdigest(),
        "duration_seconds": 10.0,
        "resolve_seconds": 1.25,
        "download_seconds": 2.5,
        "download_mib_per_second": 3.75,
        "ffprobe_seconds": 0.4,
    }
    metadata_path = tmp_path / "media.json"
    metadata_path.write_text(json.dumps(metadata), encoding="utf-8")
    monkeypatch.setattr(
        aparat,
        "_probe_summary",
        lambda _path: ({"duration_seconds": 10.0, "container": "mp4", "audio_codec": "aac", "video_codec": "h264"}, 0.01),
    )
    monkeypatch.setattr(
        aparat,
        "resolve_aparat_media",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError("must not resolve")),
    )
    result = ensure_verified_aparat_media(
        "https://www.aparat.com/v/2ptDl",
        destination,
        metadata_path,
        expected_uid="2ptDl",
    )
    assert result["reused_verified_media"] is True
    assert result["resolve_seconds"] == 1.25
    assert result["download_seconds"] == 2.5
    assert result["download_mib_per_second"] == 3.75
    assert result["ffprobe_seconds"] == 0.4
    assert result["resume_validation_ffprobe_seconds"] >= 0
