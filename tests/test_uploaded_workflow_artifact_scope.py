from pathlib import Path


def test_uploaded_workflow_keeps_success_artifact_lean_and_audio_debug_separate():
    workflow = (
        Path(__file__).resolve().parents[1]
        / ".github/workflows/process-uploaded-video.yml"
    ).read_text(encoding="utf-8")

    assert "audio_profile:" in workflow
    assert "AUDIO_PROFILE: ${{ inputs.audio_profile }}" in workflow
    assert '--audio-profile "$AUDIO_PROFILE"' in workflow

    success = workflow.split("- name: Upload transcript result", 1)[1].split("- name:", 1)[0]
    assert "uploaded-transcript-${{ inputs.request_id }}" in success
    assert "transcript-artifact/*" in success
    assert "outputs/**" not in success
    assert "audio-quality.json" not in success

    debug = workflow.split("- name: Upload debug package", 1)[1].split("- name:", 1)[0]
    assert "outputs/**" in debug
    assert "debug-artifacts-${{ inputs.request_id }}" in debug
