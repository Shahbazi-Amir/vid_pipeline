from __future__ import annotations

from pathlib import Path

from vid_pipeline.github_client import URL_WORKFLOW, GitHubRequest, GitHubState
from vid_pipeline.github_compat import CompatibleGitHubClient


def test_completed_file_submission_gets_fresh_request(tmp_path: Path):
    client = object.__new__(CompatibleGitHubClient)
    client.state = GitHubState(tmp_path / "state")
    media = tmp_path / "clip.wav"
    media.write_bytes(b"audio fixture")

    first = client.create_file_request(media)
    first.status = "completed"
    first.workflow_run_id = 123
    first.dispatch_id = "old-attempt"
    client.state.save(first)

    second = client.create_file_request(media)

    assert second.request_id != first.request_id
    assert second.status == "discovered"
    assert second.workflow_run_id == 0
    assert second.dispatch_id == ""
    assert second.sha256 == first.sha256
    assert second.file_size == first.file_size


def test_failed_file_submission_remains_resumable(tmp_path: Path):
    client = object.__new__(CompatibleGitHubClient)
    client.state = GitHubState(tmp_path / "state")
    media = tmp_path / "clip.wav"
    media.write_bytes(b"audio fixture")

    first = client.create_file_request(media)
    first.status = "workflow_failed"
    first.asset_id = 20
    client.state.save(first)

    resumed = client.create_file_request(media)

    assert resumed.request_id == first.request_id
    assert resumed.status == "workflow_failed"
    assert resumed.asset_id == 20


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


def test_url_workflow_keeps_correlation_and_lean_success_artifact():
    workflow = (
        Path(__file__).resolve().parents[1] / ".github/workflows/process-video.yml"
    ).read_text(encoding="utf-8")

    assert "dispatch_id:" in workflow
    assert "Video URL ${{ inputs.request_id || github.run_id }} — attempt" in workflow
    assert "audio_profile:" in workflow
    assert "AUDIO_PROFILE: ${{ inputs.audio_profile || 'safe' }}" in workflow
    assert '--audio-profile "$AUDIO_PROFILE"' in workflow

    success = workflow.split("- name: Upload transcript package", 1)[1].split("- name:", 1)[0]
    assert "name: transcript-${{ github.run_id }}" in success
    assert "path: transcript-artifact/*" in success
    assert "outputs/**" not in success

    debug = workflow.split("- name: Upload debug package", 1)[1].split("- name:", 1)[0]
    assert "debug-artifacts-${{ github.run_id }}" in debug
    assert "outputs/**" in debug
