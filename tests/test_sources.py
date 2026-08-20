from __future__ import annotations

import io
import json
from pathlib import Path
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from vid_pipeline.server.api import create_app
from vid_pipeline.server.queue import InlineJobQueue
from vid_pipeline.server.repository import Repository
from vid_pipeline.server.sources import (
    SourceMaterializer,
    normalize_source_request,
    validate_public_url,
)
from vid_pipeline.server.storage import LocalArtifactStore


class Response(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *_args):
        self.close()


def _repo(tmp_path: Path) -> Repository:
    return Repository(f"sqlite:///{tmp_path / 'db.sqlite'}")


def test_url_validation_blocks_private_and_internal_targets() -> None:
    for value in (
        "http://127.0.0.1/a.mp3",
        "http://10.0.0.1/a.mp3",
        "http://169.254.169.254/latest/meta-data",
        "http://localhost/a.mp3",
        "http://service.internal/a.mp3",
        "http://user:pass@example.com/a.mp3",
    ):
        with pytest.raises(ValueError):
            validate_public_url(value, resolve_dns=False)


def test_dns_resolution_cannot_rebind_to_private_ip() -> None:
    def resolver(*_args, **_kwargs):
        return [(2, 1, 6, "", ("192.168.1.5", 443))]

    with pytest.raises(ValueError, match="private/non-public"):
        validate_public_url("https://example.com/a.mp3", resolver=resolver)


def test_normalize_upload_url_and_release_sources(tmp_path: Path) -> None:
    repository = _repo(tmp_path)
    repository.put_upload(
        {
            "upload_id": "up1",
            "status": "uploaded",
            "file_name": "a.mp3",
            "file_size": 3,
            "sha256": "a" * 64,
            "object_key": "objects/a/a.mp3",
        }
    )
    upload = normalize_source_request({"source": {"type": "upload", "upload_id": "up1"}}, repository)
    assert upload["type"] == "upload"
    url = normalize_source_request(
        {"source": {"type": "url", "url": "https://example.com/audio.mp3"}}, repository
    )
    assert url == {"type": "url", "url": "https://example.com/audio.mp3"}
    release = normalize_source_request(
        {
            "source": {
                "type": "github_release",
                "repository": "owner/repo",
                "tag": "v1",
                "asset": "audio.mp3",
            }
        },
        repository,
    )
    assert release["repository"] == "owner/repo"
    assert release["asset"] == "audio.mp3"


def test_url_materializer_uses_downloader_and_stamps_hash(tmp_path: Path, monkeypatch) -> None:
    repository = _repo(tmp_path)
    storage = LocalArtifactStore(tmp_path / "storage")
    called: list[str] = []

    def downloader(url: str, directory: Path):
        called.append(url)
        path = directory / "media.mp3"
        path.write_bytes(b"abc")
        return path, {"title": "fixture"}

    import vid_pipeline.server.sources as module

    monkeypatch.setattr(module, "validate_public_url", lambda value, **_kwargs: value)
    job = {"source": {"type": "url", "url": "https://example.com/a.mp3"}}
    media = SourceMaterializer(repository, storage, url_downloader=downloader).materialize(
        job, tmp_path / "work"
    )
    assert media.read_bytes() == b"abc"
    assert called == ["https://example.com/a.mp3"]
    assert job["source_materialization"]["type"] == "url"
    assert len(job["source_materialization"]["sha256"]) == 64


def test_github_release_materializer_downloads_exact_asset(tmp_path: Path) -> None:
    repository = _repo(tmp_path)
    storage = LocalArtifactStore(tmp_path / "storage")
    release = {
        "id": 10,
        "assets": [
            {
                "id": 20,
                "name": "audio.mp3",
                "size": 3,
                "url": "https://api.github.com/repos/owner/repo/releases/assets/20",
            }
        ],
    }
    calls: list[str] = []

    def opener(request, timeout):
        calls.append(request.full_url)
        if "/releases/tags/" in request.full_url:
            assert timeout == 60
            return Response(json.dumps(release).encode())
        assert timeout == 120
        assert request.headers["Accept"] == "application/octet-stream"
        return Response(b"abc")

    job = {
        "source": {
            "type": "github_release",
            "repository": "owner/repo",
            "tag": "v1",
            "asset": "audio.mp3",
        }
    }
    media = SourceMaterializer(repository, storage, opener=opener).materialize(job, tmp_path / "work")
    assert media.read_bytes() == b"abc"
    assert len(calls) == 2
    assert job["source_materialization"]["asset_id"] == 20


def test_api_queues_url_and_release_without_actions(tmp_path: Path) -> None:
    repository = _repo(tmp_path)
    storage = LocalArtifactStore(tmp_path / "storage")
    queue = InlineJobQueue()
    client = TestClient(create_app(repository=repository, storage=storage, queue=queue))

    response = client.post(
        "/v1/jobs",
        json={"source": {"type": "url", "url": "https://example.com/a.mp3"}},
    )
    assert response.status_code == 200
    assert response.json()["source"]["type"] == "url"

    response = client.post(
        "/v1/jobs",
        json={
            "source": {
                "type": "github_release",
                "repository": "owner/repo",
                "tag": "v1",
                "asset": "a.mp3",
            }
        },
    )
    assert response.status_code == 200
    assert response.json()["source"]["type"] == "github_release"
    assert len(queue.enqueued) == 2
