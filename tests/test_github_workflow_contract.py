from __future__ import annotations

import json
from pathlib import Path

import httpx

from vid_pipeline.github_client import GitHubClient, GitHubRequest


def test_uploaded_workflow_accepts_client_string_boolean():
    workflow = (
        Path(__file__).resolve().parents[1]
        / ".github/workflows/process-uploaded-video.yml"
    ).read_text(encoding="utf-8")

    no_editorial_block = workflow.split("      no_editorial:", 1)[1].split(
        "      editorial_model:", 1
    )[0]
    assert 'default: "true"' in no_editorial_block
    assert "type: string" in no_editorial_block
    assert "if: inputs.no_editorial == 'false'" in workflow


def test_dispatch_payload_matches_workflow_contract(tmp_path: Path):
    captured: dict[str, object] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured.update(json.loads(request.read()))
        return httpx.Response(204)

    client = GitHubClient(
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
    assert inputs["no_editorial"] == "true"
    assert request.status == "queued"
