from __future__ import annotations

import json
from argparse import Namespace
from unittest.mock import patch

from vid_pipeline.cli import _transcription_config, build_parser
from vid_pipeline.pre_review import PreReviewError
from vid_pipeline.reliable_cli import (
    _accuracy_config,
    _postprocess_with_review,
    _run_url_with_review,
    reliable_editorial_config,
)


def _pipeline_args(**overrides) -> Namespace:
    values = {
        "profile": "balanced", "model": "", "device": "cpu", "compute_type": "int8",
        "language": "fa", "beam_size": 5, "initial_prompt": "", "hotwords": "",
        "max_paragraph_words": 90, "no_editorial": True, "title": "", "source_url": "",
        "url": "", "editorial_model": "unused", "editorial_base_url": "",
        "editorial_chunk_chars": 2000, "editorial_max_output_tokens": 1024,
        "guest": "", "speaker": [], "editorial_context": "", "program": "",
        "network": "", "date": "", "duration": "",
    }
    values.update(overrides)
    return Namespace(**values)


def test_run_file_profile_models_and_explicit_override(tmp_path) -> None:
    parser = build_parser()
    expected = {"fast": "small", "balanced": "large-v3-turbo", "accurate": "large-v3"}
    for profile, model in expected.items():
        args = parser.parse_args(["run-file", str(tmp_path / "input.wav"), "--profile", profile])
        assert args.model == ""
        assert _transcription_config(args).model == model
    args = parser.parse_args([
        "run-file", str(tmp_path / "input.wav"), "--profile", "fast", "--model", "custom-model"
    ])
    assert _transcription_config(args).model == "custom-model"


def test_reliable_editorial_config_caps_cpu_heavy_values() -> None:
    args = Namespace(
        editorial_model="qwen3:8b",
        editorial_base_url="http://127.0.0.1:11434",
        editorial_chunk_chars=7000,
        editorial_max_output_tokens=12000,
    )

    config = reliable_editorial_config(args)

    assert config.chunk_chars == 3500
    assert config.max_output_tokens == 4500
    assert config.context_window == 8192
    assert config.timeout_seconds == 900
    assert config.retries == 2
    assert config.second_pass is False


def test_reliable_editorial_config_preserves_smaller_values() -> None:
    args = Namespace(
        editorial_model="qwen3:0.6b",
        editorial_base_url="http://localhost:11434",
        editorial_chunk_chars=2400,
        editorial_max_output_tokens=3000,
    )

    config = reliable_editorial_config(args)

    assert config.chunk_chars == 2400
    assert config.max_output_tokens == 3000


def test_long_video_accuracy_defaults_to_targeted_fast_mode(monkeypatch) -> None:
    args = Namespace(
        model="large-v3-turbo",
        device="cpu",
        compute_type="int8",
        language="fa",
        beam_size=5,
    )
    monkeypatch.delenv("VID_PIPELINE_ACCURACY_MODE", raising=False)
    monkeypatch.delenv("VID_PIPELINE_MAX_TARGETED_SEGMENTS", raising=False)

    config = _accuracy_config(args)

    assert config.mode == "fast"
    assert config.max_targeted_segments == 40


def test_accuracy_failure_is_fatal_by_default(tmp_path, monkeypatch) -> None:
    args = Namespace(
        url="https://example.com/video.mp4",
        output_root=tmp_path,
        name="failure",
    )
    pipeline_root = tmp_path / "failure-5b487fbc"
    pipeline_root.mkdir(parents=True)
    (pipeline_root / "result.json").write_text("{}", encoding="utf-8")
    (pipeline_root / "state.json").write_text(
        '{"stages":{"accuracy":{"status":"pending"}}}', encoding="utf-8"
    )
    monkeypatch.delenv("VID_PIPELINE_ACCURACY_REQUIRED", raising=False)
    with (
        patch("vid_pipeline.reliable_cli._ORIGINAL_RUN_URL", return_value=0),
        patch("vid_pipeline.reliable_cli.VideoPipeline") as pipeline_class,
        patch("vid_pipeline.reliable_cli._accuracy_config"),
        patch(
            "vid_pipeline.reliable_cli.build_accuracy_package",
            side_effect=RuntimeError("accuracy crashed"),
        ),
    ):
        pipeline_class.return_value.paths.job_root = pipeline_root
        assert _run_url_with_review(args) == 1
    result = json.loads((pipeline_root / "result.json").read_text(encoding="utf-8"))
    assert result["status"] == "failed"
    assert result["accuracy_status"] == "failed"
    assert "accuracy crashed" in result["accuracy_error"]
    state = json.loads((pipeline_root / "state.json").read_text(encoding="utf-8"))
    assert state["stages"]["accuracy"]["status"] == "failed"


def test_accuracy_failure_updates_state_and_is_optional_when_configured(tmp_path, monkeypatch) -> None:
    root = tmp_path / "job"
    root.mkdir()
    (root / "result.json").write_text('{"status":"machine_processing_complete"}', encoding="utf-8")
    (root / "state.json").write_text(
        '{"stages":{"accuracy":{"status":"pending"},"pre_review":{"status":"pending"},"review":{"status":"pending"}}}',
        encoding="utf-8",
    )
    pipeline = Namespace(paths=Namespace(job_root=root))
    monkeypatch.setenv("VID_PIPELINE_ACCURACY_REQUIRED", "false")
    with (
        patch("vid_pipeline.reliable_cli.build_accuracy_package", side_effect=RuntimeError("optional failure")),
        patch("vid_pipeline.reliable_cli.build_pre_review_package", return_value={}),
        patch("vid_pipeline.reliable_cli.build_review_package", return_value={}),
        patch("vid_pipeline.reliable_cli.build_chatgpt_handoff", return_value={}),
        patch("vid_pipeline.reliable_cli.export_final_outputs", return_value={}),
    ):
        assert _postprocess_with_review(pipeline, _pipeline_args()) == 0
    result = json.loads((root / "result.json").read_text(encoding="utf-8"))
    state = json.loads((root / "state.json").read_text(encoding="utf-8"))
    assert result["status"] == "machine_processing_complete"
    assert result["accuracy_status"] == "failed"
    assert state["stages"]["accuracy"]["status"] == "failed"


def test_review_failure_sets_overall_result_and_state(tmp_path, monkeypatch) -> None:
    root = tmp_path / "job"
    root.mkdir()
    (root / "result.json").write_text('{"status":"machine_processing_complete"}', encoding="utf-8")
    (root / "state.json").write_text(
        '{"stages":{"accuracy":{"status":"pending"},"pre_review":{"status":"pending"},"review":{"status":"pending"}}}',
        encoding="utf-8",
    )
    pipeline = Namespace(paths=Namespace(job_root=root))
    with (
        patch("vid_pipeline.reliable_cli.build_accuracy_package", return_value={"files": {"json": "x"}}),
        patch("vid_pipeline.reliable_cli.advise_disagreements", return_value={}),
        patch("vid_pipeline.reliable_cli.build_accuracy_review", return_value={}),
        patch("vid_pipeline.reliable_cli.rebuild_from_accuracy", return_value={}),
        patch(
            "vid_pipeline.reliable_cli.build_pre_review_package",
            side_effect=PreReviewError("review failed"),
        ),
    ):
        assert _postprocess_with_review(pipeline, _pipeline_args()) == 1
    result = json.loads((root / "result.json").read_text(encoding="utf-8"))
    state = json.loads((root / "state.json").read_text(encoding="utf-8"))
    assert result["status"] == result["review_status"] == "failed"
    assert state["stages"]["pre_review"]["status"] == "failed"
