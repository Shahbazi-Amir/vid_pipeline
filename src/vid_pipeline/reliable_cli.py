"""Reliable CLI defaults plus automatic auditable human-review packaging."""

from __future__ import annotations

import json
import os
import sys
from argparse import Namespace
from pathlib import Path

from vid_pipeline import cli as base_cli
from vid_pipeline.editorial import EditorialConfig
from vid_pipeline.review import ReviewConfig, ReviewError, build_review_package
from vid_pipeline.standalone import VideoPipeline

_MAX_EDITORIAL_CHARS = 3500
_MAX_OUTPUT_TOKENS = 4500
_CONTEXT_WINDOW = 8192
_TIMEOUT_SECONDS = 900
_RETRIES = 2
_ORIGINAL_RUN_URL = base_cli.command_run_url


def reliable_editorial_config(args: Namespace) -> EditorialConfig:
    """Build a CPU-safe Ollama configuration without changing CLI arguments."""

    chunk_chars = max(2000, min(int(args.editorial_chunk_chars), _MAX_EDITORIAL_CHARS))
    max_output_tokens = max(1024, min(int(args.editorial_max_output_tokens), _MAX_OUTPUT_TOKENS))
    return EditorialConfig(
        model=args.editorial_model,
        base_url=args.editorial_base_url,
        chunk_chars=chunk_chars,
        max_output_tokens=max_output_tokens,
        context_window=_CONTEXT_WINDOW,
        timeout_seconds=_TIMEOUT_SECONDS,
        retries=_RETRIES,
        second_pass=False,
    )


def _env_float(name: str, default: float) -> float:
    raw = os.getenv(name, "").strip()
    return float(raw) if raw else default


def _default_glossaries() -> list[Path]:
    explicit = [
        Path(item.strip())
        for item in os.getenv("VID_PIPELINE_GLOSSARIES", "").split(os.pathsep)
        if item.strip()
    ]
    if explicit:
        return explicit
    directory = Path(os.getenv("VID_PIPELINE_GLOSSARY_DIR", "glossaries"))
    return sorted(directory.glob("*.json")) if directory.exists() else []


def _run_url_with_review(args: Namespace) -> int:
    result = _ORIGINAL_RUN_URL(args)
    if result != 0:
        return result
    pipeline = VideoPipeline(args.url, args.output_root, args.name)
    config = ReviewConfig(
        confidence_threshold=_env_float("VID_PIPELINE_REVIEW_CONFIDENCE", 0.68),
        segment_logprob_threshold=_env_float("VID_PIPELINE_REVIEW_LOGPROB", -0.85),
        clip_context_seconds=_env_float("VID_PIPELINE_REVIEW_CLIP_CONTEXT", 3.0),
        extract_clips=os.getenv("VID_PIPELINE_REVIEW_CLIPS", "1") not in {"0", "false", "False"},
        retranscribe_model=os.getenv("VID_PIPELINE_RETRANSCRIBE_MODEL", "").strip(),
        retranscribe_device=os.getenv("VID_PIPELINE_RETRANSCRIBE_DEVICE", "cpu").strip(),
        retranscribe_compute_type=os.getenv(
            "VID_PIPELINE_RETRANSCRIBE_COMPUTE_TYPE", "int8"
        ).strip(),
    )
    try:
        manifest = build_review_package(
            pipeline.paths.job_root,
            config=config,
            glossary_paths=_default_glossaries(),
        )
    except ReviewError as exc:
        print(f"error: human-review stage failed: {exc}", file=sys.stderr)
        return 1
    print(json.dumps({"review_stage": manifest}, ensure_ascii=False, indent=2))
    return 0


def main() -> int:
    """Run the original pipeline, then always build a human-review package."""

    base_cli._editorial_config = reliable_editorial_config
    base_cli.command_run_url = _run_url_with_review
    return base_cli.main()


if __name__ == "__main__":
    raise SystemExit(main())
