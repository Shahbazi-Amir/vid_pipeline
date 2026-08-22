from pathlib import Path


def test_release_worker_is_single_pass_local_only_and_preserves_raw_json() -> None:
    script = Path("scripts/process_private_release_asset.sh").read_text(encoding="utf-8")
    assert "rm -rf outputs" not in script
    assert "vid-pipeline run-file" not in script
    assert "transcribe_audio(" in script
    assert "normalize_audio(" in script
    assert "clean_transcript(" in script
    assert 'AsrModelManager().provision("large-v3-turbo")' in script
    assert "HF_HUB_OFFLINE=1" in script
    assert 'model=model_path' in script
    assert '"mode": "single_pass_base_transcription"' in script
    assert 'transcript.raw.json' in script
    assert '"$COLLECTION_ROOT/json/$RESULT_NUMBER.json"' in script
    assert "review deferred" in script


def test_release_workflow_is_cached_parallel_single_pass_and_complete() -> None:
    workflow = Path(".github/workflows/transcribe-release-my-parallel.yml").read_text(encoding="utf-8")
    assert "pull_request:" in workflow
    assert "actions/cache@v4" in workflow
    assert "fail-on-cache-miss: true" in workflow
    assert "max-parallel: 4" in workflow
    assert "TRANSCRIPTION_MODEL: large-v3-turbo" in workflow
    assert 'tee "$log"' in workflow
    assert "previous_indices" in workflow
    assert "already_completed" in workflow
    assert "single_pass_base_transcription" in workflow
    assert 'root / "raw" / "json"' in workflow
    assert "outputs/release-my/raw/json" in workflow
    assert "Fail run when any release asset is missing" in workflow
    assert workflow.count("sparse-checkout: |") == 4
