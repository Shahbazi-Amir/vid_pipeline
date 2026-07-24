from __future__ import annotations

from argparse import Namespace

from vid_pipeline.reliable_cli import reliable_editorial_config


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
