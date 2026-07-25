from __future__ import annotations

import json
from argparse import Namespace
from unittest.mock import patch

from vid_pipeline.reliable_cli import _run_url_with_review, reliable_editorial_config


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


def test_accuracy_failure_is_fatal_by_default(tmp_path, monkeypatch) -> None:
    args = Namespace(
        url="https://example.com/video.mp4",
        output_root=tmp_path,
        name="failure",
    )
    pipeline_root = tmp_path / "failure-5b487fbc"
    pipeline_root.mkdir(parents=True)
    (pipeline_root / "result.json").write_text("{}", encoding="utf-8")
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
    assert result["accuracy_status"] == "failed"
    assert "accuracy crashed" in result["accuracy_error"]
