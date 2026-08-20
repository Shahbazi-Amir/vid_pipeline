from __future__ import annotations

import io
from pathlib import Path

import pytest

from vid_pipeline.server.repository import ConcurrentUpdateError, Repository
from vid_pipeline.server.sources import SourceMaterializer
from vid_pipeline.server.storage import S3ArtifactStore


class FakePaginator:
    def __init__(self, client) -> None:
        self.client = client

    def paginate(self, *, Bucket: str, Prefix: str):
        yield {
            "Contents": [
                {"Key": key}
                for (bucket, key), _value in self.client.objects.items()
                if bucket == Bucket and key.startswith(Prefix)
            ]
        }


class FakeS3Client:
    def __init__(self) -> None:
        self.objects: dict[tuple[str, str], bytes] = {}

    def upload_file(self, filename: str, bucket: str, key: str) -> None:
        self.objects[(bucket, key)] = Path(filename).read_bytes()

    def download_file(self, bucket: str, key: str, filename: str) -> None:
        Path(filename).write_bytes(self.objects[(bucket, key)])

    def head_object(self, *, Bucket: str, Key: str):
        return {"ContentLength": len(self.objects[(Bucket, Key)])}

    def get_object(self, *, Bucket: str, Key: str):
        return {"Body": io.BytesIO(self.objects[(Bucket, Key)])}

    def get_paginator(self, name: str):
        assert name == "list_objects_v2"
        return FakePaginator(self)


def test_s3_store_put_materialize_size_open_and_list(tmp_path: Path) -> None:
    client = FakeS3Client()
    store = S3ArtifactStore("bucket", client=client)
    source = tmp_path / "source.bin"
    source.write_bytes(b"payload")

    assert store.put_file(source, "jobs/1/result.bin") == "jobs/1/result.bin"
    assert store.size("jobs/1/result.bin") == 7
    assert store.open("jobs/1/result.bin").read() == b"payload"
    assert store.list("jobs/1") == ["jobs/1/result.bin"]

    destination = tmp_path / "materialized" / "input.bin"
    assert store.materialize("jobs/1/result.bin", destination) == destination
    assert destination.read_bytes() == b"payload"
    assert not destination.with_suffix(".bin.part").exists()


def test_upload_source_materializes_from_s3_and_verifies_hash(tmp_path: Path) -> None:
    import hashlib

    database = Repository(f"sqlite:///{tmp_path / 'db.sqlite'}")
    client = FakeS3Client()
    store = S3ArtifactStore("bucket", client=client)
    content = b"remote-media"
    key = "objects/hash/audio.mp3"
    client.objects[("bucket", key)] = content
    database.put_upload(
        {
            "upload_id": "up",
            "status": "uploaded",
            "file_name": "audio.mp3",
            "file_size": len(content),
            "sha256": hashlib.sha256(content).hexdigest(),
            "object_key": key,
        }
    )
    job = {"source": {"type": "upload", "upload_id": "up"}}
    path = SourceMaterializer(database, store).materialize(job, tmp_path / "work")
    assert path.read_bytes() == content
    assert job["source_materialization"]["sha256"] == hashlib.sha256(content).hexdigest()


def test_stale_job_snapshot_cannot_overwrite_newer_state(tmp_path: Path) -> None:
    repository = Repository(f"sqlite:///{tmp_path / 'db.sqlite'}")
    job = {"job_id": "job", "status": "queued"}
    repository.put_job(job)
    assert job["_revision"] == 1

    worker_snapshot = repository.job("job")
    api_snapshot = repository.job("job")
    assert worker_snapshot and api_snapshot

    api_snapshot["status"] = "cancelled"
    repository.put_job(api_snapshot)
    assert api_snapshot["_revision"] == 2

    worker_snapshot["status"] = "completed"
    with pytest.raises(ConcurrentUpdateError, match="stale job revision"):
        repository.put_job(worker_snapshot)
    assert repository.job("job")["status"] == "cancelled"


def test_atomic_transition_rejects_invalid_status(tmp_path: Path) -> None:
    repository = Repository(f"sqlite:///{tmp_path / 'db.sqlite'}")
    job = {"job_id": "job", "status": "completed"}
    repository.put_job(job)

    with pytest.raises(ConcurrentUpdateError, match="cannot make this transition"):
        repository.transition_job(
            "job",
            expected_statuses={"queued", "processing"},
            updates={"status": "cancelled"},
        )
    assert repository.job("job")["status"] == "completed"
