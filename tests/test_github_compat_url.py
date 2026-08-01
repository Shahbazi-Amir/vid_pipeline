from __future__ import annotations

import json
from pathlib import Path

from vid_pipeline.github_client import GitHubRequest, GitHubState, URL_WORKFLOW
from vid_pipeline.github_compat import CompatibleGitHubClient


def test_dispatch_url_records_correlation_and_input(tmp_path: Path):
    client = object.__new__(CompatibleGitHubClient)
    client.repository = "owner/repo"
    client.ref = "feature/audio-input-support"
    client.state = GitHubState(tmp_path / "state")
    calls: list[dict] = []

    class Response:
        content = b""
        headers = {"Date": "Sat, 01 Aug 2026 21:30:00 GMT"}

    def request(method, url, **kwargs):
        calls.append({"method": method, "url": url, **kwargs})
        return Response()

    client._request = request
    request_state = GitHubRequest(request_id="request-1")

    client.dispatch_url(
        "https://example.test/audio.mp3",
        request_state,
        {"model": "small", "audio_profile": "safe"},
    )

    assert request_state.workflow_name == URL_WORKFLOW
    assert request_state.dispatch_id
    assert request_state.dispatch_started_at
    assert request_state.dispatch_server_at == "2026-08-01T21:30:00+00:00"
    assert request_state.status == "queued"
    payload = calls[0]["json"]
    assert payload["ref"] == "feature/audio-input-support"
    assert payload["inputs"]["request_id"] == "request-1"
    assert payload["inputs"]["dispatch_id"] == request_state.dispatch_id
    assert payload["inputs"]["audio_profile"] == "safe"


def test_find_url_run_uses_url_specific_title(tmp_path: Path):
    client = object.__new__(CompatibleGitHubClient)
    client.repository = "owner/repo"
    client.ref = "feature/audio-input-support"
    client.state = GitHubState(tmp_path / "state")
    request_state = GitHubRequest(
        request_id="request-1",
        workflow_name=URL_WORKFLOW,
        dispatch_id="attempt-1",
        dispatch_started_at="2026-08-01T21:30:00+00:00",
    )
    run = {
        "id": 77,
        "display_title": "Video URL request-1 — attempt attempt-1",
        "event": "workflow_dispatch",
        "head_branch": "feature/audio-input-support",
        "path": ".github/workflows/process-video.yml",
        "created_at": "2026-08-01T21:30:10Z",
        "html_url": "https://github.test/run/77",
    }

    class Response:
        def json(self):
            return {"workflow_runs": [run]}

    client._request = lambda *args, **kwargs: Response()

    assert client.find_run(request_state) == run
    assert request_state.workflow_run_id == 77
    assert request_state.workflow_run_url == "https://github.test/run/77"


def test_url_workflow_scopes_dispatched_artifact_to_request():
    workflow = (
        Path(__file__).resolve().parents[1] / ".github/workflows/process-video.yml"
    ).read_text(encoding="utf-8")

    assert "dispatch_id:" in workflow
    assert "Video URL ${{ inputs.request_id || github.run_id }} — attempt" in workflow
    assert "name: Verify dispatched result belongs to request" in workflow
    assert "reviewed-transcript-${{ inputs.request_id }}" in workflow
    assert "outputs/${{ inputs.request_id }}-*/result.json" in workflow
    assert "outputs/${{ inputs.request_id }}-*/audio/audio-quality.json" in workflow
