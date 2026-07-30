from __future__ import annotations

import json
from pathlib import Path

import httpx
import pytest

from vid_pipeline.github_client import GitHubRequest
from vid_pipeline.github_compat import CompatibleGitHubClient


def _workflow_text() -> str:
    return (
        Path(__file__).resolve().parents[1]
        / ".github/workflows/process-uploaded-video.yml"
    ).read_text(encoding="utf-8")


def test_uploaded_workflow_uses_bounded_string_inputs():
    workflow = _workflow_text()
    inputs_block = workflow.split("    inputs:", 1)[1].split("\n\npermissions:", 1)[0]
    input_names = [
        line.strip()[:-1]
        for line in inputs_block.splitlines()
        if line.startswith("      ") and not line.startswith("        ")
    ]

    assert len(input_names) == 10
    assert "release_id" not in input_names
    assert "editorial_model" not in input_names

    no_editorial_block = inputs_block.split("      no_editorial:", 1)[1]
    assert 'default: "true"' in no_editorial_block
    assert "type: string" in no_editorial_block
    assert "if: inputs.no_editorial == 'false'" in workflow
    assert "EDITORIAL_MODEL: qwen3:8b" in workflow


def test_uploaded_workflow_does_not_use_runner_context_in_job_env():
    workflow = _workflow_text()
    job_env = workflow.split("    env:", 1)[1].split("\n\n    steps:", 1)[0]

    assert "runner.temp" not in job_env
    assert "INPUT_MEDIA: /tmp/vid-pipeline-input/media" in job_env
    assert "find /tmp/vid-pipeline-input" in workflow


def test_dispatch_payload_matches_workflow_contract(tmp_path: Path):
    captured: dict[str, object] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured.update(json.loads(request.read()))
        return httpx.Response(204)

    client = CompatibleGitHubClient(
        "test-token",
        "owner/repo",
        state_root=tmp_path / "state",
        output_root=tmp_path / "outputs",
        retries=0,
        transport=httpx.MockTransport(handler),
    )
    request = GitHubRequest(
        request_id="request-1",
        release_id=10,
        asset_id=20,
        safe_asset_name="vp-test-clip.mp4",
        original_name="clip.mp4",
        file_size=123,
        sha256="abc",
        status="uploaded",
    )

    client.dispatch_upload(request, {"no_editorial": True})

    inputs = captured["inputs"]
    assert isinstance(inputs, dict)
    assert len(inputs) == 10
    assert "release_id" not in inputs
    assert inputs["no_editorial"] == "true"
    assert request.status == "queued"


def test_github_http_error_includes_status_and_message(tmp_path: Path):
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            422,
            json={
                "message": "Validation Failed",
                "errors": [{"resource": "WorkflowDispatch", "field": "inputs"}],
            },
        )

    client = CompatibleGitHubClient(
        "test-token",
        "owner/repo",
        state_root=tmp_path / "state",
        output_root=tmp_path / "outputs",
        retries=2,
        transport=httpx.MockTransport(handler),
    )

    with pytest.raises(RuntimeError, match=r"HTTP 422: Validation Failed.*inputs"):
        client._request("POST", "/test")
