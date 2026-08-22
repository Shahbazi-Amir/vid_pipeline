from pathlib import Path


def test_release_worker_uses_isolated_output_root_and_controlled_model() -> None:
    script = Path("scripts/process_private_release_asset.sh").read_text(encoding="utf-8")
    assert '--output-root "$RUN_OUTPUT_ROOT"' in script
    assert 'find "$RUN_OUTPUT_ROOT"' in script
    assert "rm -rf outputs" not in script
    assert '--model "$MODEL_PATH"' in script
    assert 'AsrModelManager().provision("large-v3-turbo")' in script
    assert "HF_HUB_OFFLINE=1" in script
    assert "large-v3-turbo" in script


def test_release_workflow_is_cached_parallel_and_live_logged() -> None:
    workflow = Path(".github/workflows/transcribe-release-my-parallel.yml").read_text(encoding="utf-8")
    assert "pull_request:" in workflow
    assert "actions/cache@v4" in workflow
    assert "fail-on-cache-miss: true" in workflow
    assert "max-parallel: 4" in workflow
    assert "TRANSCRIPTION_MODEL: large-v3-turbo" in workflow
    assert 'tee "$log"' in workflow
    assert "previous_indices" in workflow
    assert "already_completed" in workflow
    assert 'raw" / "timestamped"' in workflow
    assert "Fail run when any release asset is missing" in workflow
    assert workflow.count("sparse-checkout: |") == 4
