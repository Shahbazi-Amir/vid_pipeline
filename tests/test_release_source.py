from __future__ import annotations

import hashlib
import io
import json
from pathlib import Path
from unittest.mock import patch
from urllib.error import HTTPError, URLError

import pytest

from vid_pipeline.cli import build_parser
from vid_pipeline.errors import PipelineError
from vid_pipeline.release_source import (
    ReleaseAsset,
    download_release_asset,
    resolve_release_asset,
)
from vid_pipeline.standalone import LocalMediaPipeline


class Response(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *_args):
        self.close()


def release_payload(content: bytes = b"audio") -> dict:
    return {
        "id": 12,
        "name": "Audio input",
        "tag_name": "audio-v1",
        "assets": [
            {
                "id": 34,
                "name": "speech.mp3",
                "state": "uploaded",
                "size": len(content),
                "digest": f"sha256:{hashlib.sha256(content).hexdigest()}",
                "browser_download_url": "https://github.com/example/media/releases/download/audio-v1/speech.mp3",
            }
        ],
    }


def test_release_asset_resolution_is_exact_and_records_provenance() -> None:
    response = Response(json.dumps(release_payload()).encode())
    with patch("urllib.request.urlopen", return_value=response):
        asset = resolve_release_asset(
            "example/media", "audio-v1", asset_name="speech.mp3", token="private-token"
        )

    assert asset.asset_id == 34
    assert asset.provenance()["source"] == "github_release"
    assert asset.provenance()["repository"] == "example/media"
    assert "private-token" not in json.dumps(asset.provenance())


@pytest.mark.parametrize(
    ("repository", "asset_name", "asset_id"),
    [("invalid", "speech.mp3", 0), ("example/media", "", 0), ("example/media", "x", 1)],
)
def test_release_selector_validation(repository: str, asset_name: str, asset_id: int) -> None:
    with pytest.raises(ValueError):
        resolve_release_asset(
            repository, "audio-v1", asset_name=asset_name, asset_id=asset_id
        )


def test_release_rejects_missing_or_unsupported_asset() -> None:
    payload = release_payload()
    payload["assets"][0]["name"] = "notes.txt"
    with patch("urllib.request.urlopen", return_value=Response(json.dumps(payload).encode())):
        with pytest.raises(PipelineError, match="Unsupported release media extension"):
            resolve_release_asset("example/media", "audio-v1", asset_id=34)


@pytest.mark.parametrize(
    ("error", "message"),
    [
        (HTTPError("https://api.github.test", 401, "Unauthorized", {}, None), "HTTP 401"),
        (HTTPError("https://api.github.test", 403, "Forbidden", {}, None), "HTTP 403"),
        (HTTPError("https://api.github.test", 404, "Not found", {}, None), "HTTP 404"),
        (URLError("timed out"), "URLError"),
    ],
)
def test_release_api_errors_are_clear_and_do_not_expose_credentials(
    error: Exception, message: str
) -> None:
    with patch("urllib.request.urlopen", side_effect=error):
        with pytest.raises(PipelineError, match=message) as raised:
            resolve_release_asset(
                "example/media", "audio-v1", asset_name="speech.mp3", token="private-token"
            )
    assert "private-token" not in str(raised.value)


def test_release_download_is_atomic_verified_and_reused(tmp_path: Path) -> None:
    content = b"small audio fixture"
    asset = ReleaseAsset(
        repository="example/media",
        tag="audio-v1",
        release_id=12,
        release_name="Audio input",
        asset_id=34,
        asset_name="speech.mp3",
        size=len(content),
        digest=f"sha256:{hashlib.sha256(content).hexdigest()}",
        browser_download_url="https://example.test/speech.mp3",
    )
    with patch("urllib.request.urlopen", return_value=Response(content)) as download:
        target = download_release_asset(asset, tmp_path, token="private-token")
    assert target.read_bytes() == content
    assert not list(target.parent.glob("*.part"))

    with patch("urllib.request.urlopen") as download:
        assert download_release_asset(asset, tmp_path) == target
        download.assert_not_called()


def test_release_download_rejects_size_mismatch(tmp_path: Path) -> None:
    asset = ReleaseAsset(
        repository="example/media",
        tag="audio-v1",
        release_id=12,
        release_name="",
        asset_id=34,
        asset_name="speech.mp3",
        size=20,
        digest="",
        browser_download_url="",
    )
    with patch("urllib.request.urlopen", return_value=Response(b"short")):
        with pytest.raises(PipelineError, match="size does not match"):
            download_release_asset(asset, tmp_path)


def test_release_rejects_missing_tag_unsafe_name_and_zero_size() -> None:
    with pytest.raises(ValueError, match="tag is required"):
        resolve_release_asset("example/media", "", asset_name="speech.mp3")

    for name, size, message in (
        ("../speech.mp3", 5, "unsafe filename"),
        ("speech.mp3", 0, "empty"),
    ):
        payload = release_payload()
        payload["assets"][0].update(name=name, size=size)
        with patch("urllib.request.urlopen", return_value=Response(json.dumps(payload).encode())):
            with pytest.raises(PipelineError, match=message):
                resolve_release_asset("example/media", "audio-v1", asset_id=34)


def test_release_download_enforces_maximum_and_sha(tmp_path: Path) -> None:
    content = b"audio"
    asset = ReleaseAsset(
        repository="example/media",
        tag="audio-v1",
        release_id=12,
        release_name="",
        asset_id=34,
        asset_name="speech.mp3",
        size=len(content),
        digest=f"sha256:{'0' * 64}",
        browser_download_url="",
    )
    with pytest.raises(PipelineError, match="download limit"):
        download_release_asset(asset, tmp_path, max_bytes=1)
    with patch("urllib.request.urlopen", return_value=Response(content)):
        with pytest.raises(PipelineError, match="SHA-256"):
            download_release_asset(asset, tmp_path)
    target_dir = tmp_path / "example" / "media" / "12"
    assert not (target_dir / "speech.mp3").exists()
    assert not list(target_dir.glob("*.part"))


def test_release_interrupted_download_removes_partial_file(tmp_path: Path) -> None:
    class Interrupted(Response):
        def __init__(self) -> None:
            super().__init__(b"partial")
            self.reads = 0

        def read(self, size: int = -1) -> bytes:
            self.reads += 1
            if self.reads > 1:
                raise OSError("connection reset")
            return super().read(size)

    asset = ReleaseAsset(
        repository="example/media",
        tag="audio-v1",
        release_id=12,
        release_name="",
        asset_id=34,
        asset_name="speech.mp3",
        size=20,
        digest="",
        browser_download_url="",
    )
    with patch("urllib.request.urlopen", return_value=Interrupted()):
        with pytest.raises(PipelineError, match="OSError"):
            download_release_asset(asset, tmp_path)
    target_dir = tmp_path / "example" / "media" / "12"
    assert not list(target_dir.glob("*.part"))


def test_digestless_release_cache_requires_matching_sidecar_and_sha(tmp_path: Path) -> None:
    content = b"digestless audio"
    asset = ReleaseAsset(
        repository="example/media",
        tag="audio-v1",
        release_id=12,
        release_name="",
        asset_id=34,
        asset_name="speech.mp3",
        size=len(content),
        digest="",
        browser_download_url="",
    )
    with patch("urllib.request.urlopen", return_value=Response(content)):
        target = download_release_asset(asset, tmp_path)
    sidecar = target.with_name("speech.mp3.cache.json")
    assert sidecar.is_file()

    with patch("urllib.request.urlopen") as download:
        assert download_release_asset(asset, tmp_path) == target
        download.assert_not_called()

    target.write_bytes(b"X" * len(content))
    with patch("urllib.request.urlopen", return_value=Response(content)) as download:
        assert download_release_asset(asset, tmp_path).read_bytes() == content
        download.assert_called_once()


def test_digestless_same_size_file_without_sidecar_is_redownloaded(tmp_path: Path) -> None:
    content = b"expected bytes"
    asset = ReleaseAsset(
        repository="example/media",
        tag="audio-v1",
        release_id=12,
        release_name="",
        asset_id=34,
        asset_name="speech.mp3",
        size=len(content),
        digest="",
        browser_download_url="",
    )
    target = tmp_path / "example" / "media" / "12" / "speech.mp3"
    target.parent.mkdir(parents=True)
    target.write_bytes(b"?" * len(content))
    with patch("urllib.request.urlopen", return_value=Response(content)) as download:
        assert download_release_asset(asset, tmp_path).read_bytes() == content
        download.assert_called_once()


def test_release_cli_contract() -> None:
    args = build_parser().parse_args(
        [
            "run-github-release",
            "example/media",
            "audio-v1",
            "--asset-name",
            "speech.mp3",
            "--no-editorial",
        ]
    )
    assert args.repository == "example/media"
    assert args.asset_name == "speech.mp3"
    assert args.audio_profile == "safe"


def test_local_pipeline_serializes_release_provenance(tmp_path: Path) -> None:
    source = tmp_path / "speech.mp3"
    source.write_bytes(b"fixture")
    pipeline = LocalMediaPipeline(
        source,
        tmp_path / "outputs",
        source_provenance={"source": "github_release", "asset_id": 34},
    )
    media = {
        "input_type": "audio",
        "duration_seconds": 1.0,
        "has_audio_stream": True,
    }
    with patch("vid_pipeline.media.require_decodable_audio", return_value=media):
        pipeline.inspect()
    payload = json.loads(pipeline.paths.source_metadata.read_text())
    assert payload["source"] == "github_release"
    assert payload["original_name"] == "speech.mp3"
    assert payload["provenance"] == {"source": "github_release", "asset_id": 34}
