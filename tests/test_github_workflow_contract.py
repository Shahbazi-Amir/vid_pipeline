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

    assert len(input_names) == 11
    assert "release_id" not in input_names
    assert "asset_name" not in input_names
    assert "dispatch_id" in input_names
    assert "editorial_model" not in input_names

    no_editorial_block = inputs_block.split("      no_editorial:", 1)[1]
    assert 'default: "true"' in no_editorial_block
    assert "type: string" in no_editorial_block
    assert "if: inputs.no_editorial == 'false'" in workflow
    assert "EDITORIAL_MODEL: qwen3:8b" in workflow
    model_block = inputs_block.split("      model:", 1)[1].split("      language:", 1)[0]
    assert "required: false" in model_block
    assert 'default: ""' in model_block
    assert '[[ -n "${MODEL:-}" ]] && args+=(--model "$MODEL")' in workflow
    assert '--profile "$PROFILE" --model "$MODEL"' not in workflow


def test_success_artifacts_are_lean_and_debug_is_separate() -> None:
    workflows = Path(__file__).resolve().parents[1] / ".github/workflows"
    for name in ("process-video.yml", "process-uploaded-video.yml"):
        text = (workflows / name).read_text(encoding="utf-8")
        success_block = text.split("name: Upload transcript", 1)[1].split("- name:", 1)[0]
        assert "transcript-artifact/*" in success_block
        for internal in ("state.json", "result.json", "raw/", "accuracy/", "review/", "audio/"):
            assert internal not in success_block
        assert "Upload debug package" in text
        assert "Upload failure diagnostics" in text


def test_uploaded_workflow_does_not_use_runner_context_in_job_env():
    workflow = _workflow_text()
    job_env = workflow.split("    env:", 1)[1].split("\n\n    steps:", 1)[0]

    assert "runner.temp" not in job_env
    assert "INPUT_MEDIA: /tmp/vid-pipeline-input/media" in job_env
    assert "find /tmp/vid-pipeline-input" in workflow
    assert "permissions:\n  # Draft release assets require" in workflow
    assert "  contents: write" in workflow
    assert "run-name: Uploaded video ${{ inputs.request_id }} — attempt ${{ inputs.dispatch_id }}" in workflow


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
    assert len(inputs) == 11
    assert "release_id" not in inputs
    assert "asset_name" not in inputs
    assert inputs["dispatch_id"] == request.dispatch_id
    assert request.dispatch_started_at
    assert inputs["no_editorial"] == "true"
    assert inputs["model"] == ""
    assert request.status == "queued"
    workflow = _workflow_text()
    block = workflow.split("    inputs:", 1)[1].split("\n\npermissions:", 1)[0]
    workflow_inputs = {
        line.strip()[:-1]
        for line in block.splitlines()
        if line.startswith("      ") and not line.startswith("        ")
    }
    assert set(inputs) == workflow_inputs


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


def test_runner_asset_error_includes_status_headers_and_body():
    workflow = _workflow_text()

    assert "HTTP {exc.code}" in workflow
    assert "headers={safe_headers!r}" in workflow
    assert "body={body!r}" in workflow
    assert '"authorization"' not in workflow.split("safe_headers =", 1)[1]
