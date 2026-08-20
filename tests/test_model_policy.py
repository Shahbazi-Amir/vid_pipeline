from __future__ import annotations

import hashlib
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from vid_pipeline.models import JobRequest
from vid_pipeline.profiles import (
    DEFAULT_PROFILE,
    PROFILE_MODELS,
    PROJECT_ASR_MODEL,
    SUPPORTED_PROFILES,
    normalize_profile,
    resolve_transcription_model,
)
from vid_pipeline.server.api import create_app
from vid_pipeline.server.queue import InlineJobQueue
from vid_pipeline.server.repository import Repository
from vid_pipeline.server.storage import LocalArtifactStore
from vid_pipeline.transcribe import TranscriptionConfig


def test_every_profile_resolves_to_project_controlled_model() -> None:
    assert tuple(PROFILE_MODELS) == SUPPORTED_PROFILES
    assert DEFAULT_PROFILE == "balanced"
    for profile in SUPPORTED_PROFILES:
        assert resolve_transcription_model(profile) == PROJECT_ASR_MODEL
        assert PROFILE_MODELS[profile] == PROJECT_ASR_MODEL


def test_named_models_without_controlled_artifacts_are_rejected() -> None:
    for model in ("small", "medium", "large-v3"):
        with pytest.raises(ValueError, match="unsupported ASR model"):
            resolve_transcription_model("balanced", model, allow_local_path=False)


def test_unknown_profile_is_rejected_before_model_selection() -> None:
    with pytest.raises(ValueError, match="unknown transcription profile"):
        normalize_profile("ultra")
    with pytest.raises(ValueError, match="unknown transcription profile"):
        resolve_transcription_model("ultra", PROJECT_ASR_MODEL)


def test_local_model_directory_is_local_only_escape_hatch(tmp_path: Path) -> None:
    local_model = tmp_path / "ct2-model"
    local_model.mkdir()
    assert resolve_transcription_model("fast", str(local_model)) == str(local_model.resolve())
    with pytest.raises(ValueError, match="unsupported ASR model"):
        resolve_transcription_model(
            "fast", str(local_model), allow_local_path=False
        )


def test_core_dataclass_defaults_match_model_policy() -> None:
    assert TranscriptionConfig().model == PROJECT_ASR_MODEL
    request = JobRequest("job", "file", "/input.wav")
    assert request.profile == DEFAULT_PROFILE
    assert request.asr_model == PROJECT_ASR_MODEL


@pytest.fixture
def api_services(tmp_path: Path):
    repository = Repository(f"sqlite:///{tmp_path / 'pipeline.db'}")
    storage = LocalArtifactStore(tmp_path / "storage")
    queue = InlineJobQueue()
    app = create_app(
        repository=repository,
        storage=storage,
        queue=queue,
        token="secret",
        max_file_size=1024 * 1024,
    )
    return TestClient(app), repository, queue


def _complete_upload(client: TestClient, content: bytes = b"media") -> tuple[str, dict[str, str]]:
    headers = {"Authorization": "Bearer secret"}
    digest = hashlib.sha256(content).hexdigest()
    created = client.post(
        "/v1/uploads",
        headers=headers,
        json={
            "file_name": "sample.mp3",
            "file_size": len(content),
            "sha256": digest,
            "content_type": "audio/mpeg",
        },
    )
    assert created.status_code == 200
    upload_id = created.json()["upload_id"]
    assert client.put(
        f"/v1/uploads/{upload_id}/parts/1", headers=headers, content=content
    ).status_code == 200
    assert client.post(
        f"/v1/uploads/{upload_id}/complete", headers=headers
    ).status_code == 200
    return upload_id, headers


@pytest.mark.parametrize("profile", SUPPORTED_PROFILES)
def test_api_stores_only_resolved_production_model(api_services, profile: str) -> None:
    client, repository, queue = api_services
    upload_id, headers = _complete_upload(client, content=("media-" + profile).encode())
    response = client.post(
        "/v1/jobs",
        headers=headers,
        json={"upload_id": upload_id, "profile": profile},
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["model"] == PROJECT_ASR_MODEL
    assert repository.job(payload["job_id"])["model"] == PROJECT_ASR_MODEL
    assert payload["job_id"] in queue.enqueued


def test_api_rejects_unprovisionable_model_without_enqueue(api_services) -> None:
    client, _, queue = api_services
    upload_id, headers = _complete_upload(client, content=b"bad-model")
    response = client.post(
        "/v1/jobs",
        headers=headers,
        json={"upload_id": upload_id, "profile": "fast", "model": "small"},
    )
    assert response.status_code == 422
    assert "unsupported ASR model" in response.json()["detail"]
    assert queue.enqueued == []


def test_api_rejects_unknown_profile_without_enqueue(api_services) -> None:
    client, _, queue = api_services
    upload_id, headers = _complete_upload(client, content=b"bad-profile")
    response = client.post(
        "/v1/jobs",
        headers=headers,
        json={"upload_id": upload_id, "profile": "ultra"},
    )
    assert response.status_code == 422
    assert "unknown transcription profile" in response.json()["detail"]
    assert queue.enqueued == []
