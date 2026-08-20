from __future__ import annotations

import hashlib
import importlib
import json
import sys
from pathlib import Path

import httpx
import pytest
from fastapi.testclient import TestClient

from vid_pipeline.cli import build_parser
from vid_pipeline.models import TranscriptDocument, TranscriptSegment
from vid_pipeline.online_client import ClientState, OnlineClient, discover
from vid_pipeline.server.api import create_app
from vid_pipeline.server.queue import InlineJobQueue
from vid_pipeline.server.repository import Repository
from vid_pipeline.server.storage import LocalArtifactStore
from vid_pipeline.server.worker import process_job


@pytest.fixture
def services(tmp_path: Path):
    repository = Repository(f"sqlite:///{tmp_path / 'pipeline.db'}")
    storage = LocalArtifactStore(tmp_path / "storage")
    queue = InlineJobQueue()
    app = create_app(
        repository=repository, storage=storage, queue=queue, token="secret",
        max_file_size=1024 * 1024,
    )
    return TestClient(app), repository, storage, queue


def _upload(client: TestClient, content: bytes = b"small-media"):
    digest = hashlib.sha256(content).hexdigest()
    headers = {"Authorization": "Bearer secret"}
    created = client.post("/v1/uploads", headers=headers, json={
        "file_name": "fixture.mp4", "file_size": len(content), "sha256": digest,
        "content_type": "video/mp4",
    })
    assert created.status_code == 200
    upload_id = created.json()["upload_id"]
    part = client.put(
        f"/v1/uploads/{upload_id}/parts/1", headers=headers, content=content
    )
    assert part.status_code == 200
    complete = client.post(f"/v1/uploads/{upload_id}/complete", headers=headers)
    assert complete.status_code == 200
    return upload_id, headers


def _create_job(client: TestClient, headers: dict[str, str], upload_id: str) -> str:
    response = client.post("/v1/jobs", headers=headers, json={
        "upload_id": upload_id, "profile": "fast", "model": "tiny",
        "language": "fa", "editorial": False,
    })
    assert response.status_code == 200
    return response.json()["job_id"]


def test_health_and_authentication(services):
    client, *_ = services
    assert client.get("/health").json() == {"status": "ok"}
    assert client.get("/v1/jobs").status_code == 401


def test_upload_resume_duplicate_and_hash_mismatch(services):
    client, *_ = services
    content = b"abcdefgh"
    upload_id, headers = _upload(client, content)
    status = client.get(f"/v1/uploads/{upload_id}", headers=headers).json()
    assert status["uploaded_bytes"] == len(content)
    duplicate = client.post("/v1/uploads", headers=headers, json={
        "file_name": "duplicate.mp4", "file_size": len(content),
        "sha256": hashlib.sha256(content).hexdigest(),
    })
    assert duplicate.json()["upload_id"] == upload_id
    bad = client.post("/v1/uploads", headers=headers, json={
        "file_name": "bad.mp4", "file_size": 3, "sha256": "0" * 64,
    }).json()["upload_id"]
    client.put(f"/v1/uploads/{bad}/parts/1", headers=headers, content=b"bad")
    assert client.post(f"/v1/uploads/{bad}/complete", headers=headers).status_code == 422


def test_upload_validation(services):
    client, *_ = services
    headers = {"Authorization": "Bearer secret"}
    base = {"file_size": 1, "sha256": hashlib.sha256(b"x").hexdigest()}
    assert client.post("/v1/uploads", headers=headers, json={
        **base, "file_name": "../../secret.txt"
    }).status_code == 415
    assert client.post("/v1/uploads", headers=headers, json={
        "file_name": "huge.mp4", "file_size": 2 * 1024 * 1024, "sha256": "0" * 64
    }).status_code == 413


class MockProcessor:
    def process(self, media: Path, job: dict, work: Path) -> TranscriptDocument:
        assert media.read_bytes() == b"small-media"
        return TranscriptDocument(
            job_id=job["job_id"], language="fa",
            segments=[
                TranscriptSegment(1, 0.0, 1.5, "سلام دنیا", confidence=0.98),
                TranscriptSegment(2, 1.5, 3.0, "این یک آزمون است", confidence=0.97),
            ],
        )


class LowQualityProcessor:
    def process(self, media: Path, job: dict, work: Path) -> TranscriptDocument:
        assert media.read_bytes() == b"small-media"
        return TranscriptDocument(
            job_id=job["job_id"], language="fa",
            segments=[
                TranscriptSegment(
                    1, 0.0, 2.0, "بنامه خدا حادی نجف",
                    confidence=0.20, suspicious_flags=["low_word_confidence"],
                ),
                TranscriptSegment(
                    2, 2.0, 4.0, "آقای دکتر گودی",
                    confidence=0.25, suspicious_flags=["low_word_confidence"],
                ),
            ],
        )


class RawEvidenceProcessor:
    def process(self, media: Path, job: dict, work: Path) -> TranscriptDocument:
        raw = {
            "segments": [
                {
                    "id": 1, "start": 0.0, "end": 2.0, "text": "متن مشکوک",
                    "avg_logprob": -1.6, "no_speech_prob": 0.05,
                    "words": [{"word": "مشکوک", "probability": 0.15}],
                    "review_flags": ["low_log_probability", "low_word_confidence"],
                }
            ]
        }
        (work / "transcript.raw.json").write_text(
            json.dumps(raw, ensure_ascii=False), encoding="utf-8"
        )
        return TranscriptDocument(
            job_id=job["job_id"], language="fa",
            segments=[TranscriptSegment(1, 0.0, 2.0, "متن مشکوک", confidence=0.99)],
        )


def test_end_to_end_job_and_all_final_artifacts(services, tmp_path: Path):
    client, repository, storage, queue = services
    upload_id, headers = _upload(client)
    job_id = _create_job(client, headers, upload_id)
    assert queue.enqueued == [job_id]
    job = process_job(job_id, repository, storage, MockProcessor())
    assert job["status"] == "completed"
    assert job["quality_gate"]["decision"] == "pass"
    expected = {
        "delivery/transcript.md",
        "delivery/transcript.txt",
        "delivery/transcript.timestamped.md",
    }
    assert expected == set(job["artifacts"])
    listed = client.get(f"/v1/jobs/{job_id}/artifacts", headers=headers).json()["artifacts"]
    assert expected == {item["name"] for item in listed}
    download = client.get(
        f"/v1/jobs/{job_id}/artifacts/delivery/transcript.txt", headers=headers
    )
    assert download.status_code == 200
    assert "سلام دنیا" in download.text
    quality = json.loads(storage.path(f"jobs/{job_id}/quality/quality-report.json").read_text())
    assert quality["valid"] is True
    assert quality["decision"] == "pass"
    assert client.get(
        f"/v1/jobs/{job_id}/artifacts/../../pipeline.db", headers=headers
    ).status_code == 404


def test_low_quality_transcript_cannot_be_finalized(services):
    client, repository, storage, _ = services
    upload_id, headers = _upload(client)
    job_id = _create_job(client, headers, upload_id)
    job = process_job(job_id, repository, storage, LowQualityProcessor())

    assert job["status"] == "review_required"
    assert job["current_stage"] == "quality_gate"
    assert job["quality_gate"]["decision"] == "review_required"
    assert not storage.path(f"jobs/{job_id}/delivery").exists()
    assert not storage.path(f"jobs/{job_id}/final").exists()
    assert all(not name.startswith("delivery/") for name in job["artifacts"])

    quality = json.loads(storage.path(f"jobs/{job_id}/quality/quality-report.json").read_text())
    assert quality["valid"] is False
    assert quality["overall_score"] < quality["thresholds"]["min_overall_score"]
    assert "overall_score_below_threshold" in quality["gate_reasons"]
    result = json.loads(storage.path(f"jobs/{job_id}/result.json").read_text())
    assert result["status"] == "review_required"

    listed = client.get(f"/v1/jobs/{job_id}/artifacts", headers=headers).json()["artifacts"]
    assert "quality/quality-report.json" in {item["name"] for item in listed}


def test_real_raw_asr_evidence_overrides_optimistic_document_confidence(services):
    client, repository, storage, _ = services
    upload_id, headers = _upload(client)
    job_id = _create_job(client, headers, upload_id)
    job = process_job(job_id, repository, storage, RawEvidenceProcessor())
    assert job["status"] == "review_required"
    report = json.loads(storage.path(f"jobs/{job_id}/quality/quality-report.json").read_text())
    assert report["valid"] is False
    assert report["segments"][0]["mean_word_confidence"] == 0.15


def test_cancel_and_retry(services):
    client, _, _, queue = services
    upload_id, headers = _upload(client)
    job_id = client.post(f"/v1/jobs", headers=headers, json={"upload_id": upload_id}).json()["job_id"]
    assert client.post(f"/v1/jobs/{job_id}/cancel", headers=headers).json()["status"] == "cancelled"
    retried = client.post(f"/v1/jobs/{job_id}/retry", headers=headers).json()
    assert retried["status"] == "queued"
    assert retried["retries"] == 1
    assert job_id in queue.cancelled


def test_recursive_discovery_and_state(tmp_path: Path):
    root = tmp_path / "input"
    (root / "nested").mkdir(parents=True)
    (root / "one.mp4").write_bytes(b"1")
    (root / "nested" / "two.wav").write_bytes(b"2")
    (root / "ignore.txt").write_text("x")
    assert [path.name for path in discover(root)] == ["one.mp4"]
    assert {path.name for path in discover(root, True)} == {"one.mp4", "two.wav"}
    state = ClientState(tmp_path / ".vid_pipeline")
    assert json.loads((state.root / "client.json").read_text())["schema_version"] == 1


def test_submit_commands_parse_without_worker_import():
    for name, argv in {
        "submit-file": ["submit-file", "video.mp4", "--server-url", "http://server"],
        "submit-folder": ["submit-folder", "videos", "--recursive", "--server-url", "http://server"],
        "jobs": ["jobs", "--server-url", "http://server"],
        "job-status": ["job-status", "job-1", "--server-url", "http://server"],
        "download-results": ["download-results", "job-1", "--server-url", "http://server"],
        "wait": ["wait", "job-1", "--server-url", "http://server"],
    }.items():
        assert build_parser().parse_args(argv).command == name
    sys.modules.pop("faster_whisper", None)
    importlib.import_module("vid_pipeline.online_client")
    assert "faster_whisper" not in sys.modules


def test_lightweight_client_retries_and_resumes_upload(tmp_path: Path):
    content = b"x" * 100
    media = tmp_path / "clip.mp4"
    media.write_bytes(content)
    calls = {"part": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/v1/uploads" and request.method == "POST":
            return httpx.Response(200, json={"upload_id": "up1", "uploaded_bytes": 0})
        if request.url.path == "/v1/uploads/up1" and request.method == "GET":
            return httpx.Response(200, json={"upload_id": "up1", "uploaded_bytes": 0})
        if "/parts/" in request.url.path:
            calls["part"] += 1
            if calls["part"] == 1:
                return httpx.Response(503, json={"detail": "temporary"})
            return httpx.Response(200, json={"uploaded_bytes": len(content)})
        if request.url.path.endswith("/complete"):
            return httpx.Response(200, json={"object_key": "objects/input.mp4"})
        if request.url.path == "/v1/jobs":
            return httpx.Response(200, json={"job_id": "job1", "status": "queued"})
        raise AssertionError(request.url)

    client = OnlineClient(
        "http://server", "top-secret", tmp_path / "outputs", tmp_path / ".state",
        retries=1, transport=httpx.MockTransport(handler),
    )
    record = client.submit_file(media)
    assert record.uploaded_bytes == len(content)
    assert record.job_id == "job1"
    assert calls["part"] == 2
    saved = ClientState(tmp_path / ".state").load(record.sha256)
    assert saved and saved.job_id == "job1"


def test_client_wait_returns_review_required_as_terminal(tmp_path: Path):
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/v1/jobs/job-review"
        return httpx.Response(200, json={"job_id": "job-review", "status": "review_required"})

    client = OnlineClient(
        "http://server", output_root=tmp_path / "outputs",
        state_root=tmp_path / ".state", transport=httpx.MockTransport(handler),
    )
    assert client.wait("job-review", interval=0)["status"] == "review_required"


def test_client_downloads_artifacts_to_output_root(tmp_path: Path):
    payload = b"final transcript\n"

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/artifacts"):
            return httpx.Response(200, json={
                "artifacts": [{"name": "final/transcript.final.txt", "size": len(payload)}]
            })
        if request.url.path.endswith("/final/transcript.final.txt"):
            return httpx.Response(200, content=payload)
        raise AssertionError(request.url)

    client = OnlineClient(
        "http://server", output_root=tmp_path / "outputs",
        state_root=tmp_path / ".state", transport=httpx.MockTransport(handler),
    )
    root = client.download_results("job-1")
    assert (root / "final" / "transcript.final.txt").read_bytes() == payload
