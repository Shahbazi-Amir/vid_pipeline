from pathlib import Path


def test_uploaded_workflow_scopes_artifact_to_current_request():
    workflow = (
        Path(__file__).resolve().parents[1]
        / ".github/workflows/process-uploaded-video.yml"
    ).read_text(encoding="utf-8")

    request_scoped = "outputs/${{ inputs.request_id }}-*"
    assert "name: Verify result belongs to request" in workflow
    assert f"{request_scoped}/result.json" in workflow
    assert f"{request_scoped}/source.json" in workflow
    assert f"{request_scoped}/audio/audio-quality.json" in workflow
    assert "outputs/**/result.json" not in workflow
    assert "outputs/**/source.json" not in workflow
