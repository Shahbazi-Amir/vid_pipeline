"""Reliable CLI defaults with multi-pass ASR accuracy and review packaging."""
from __future__ import annotations

import json
import os
import sys
from argparse import Namespace
from pathlib import Path

from vid_pipeline import cli as base_cli
from vid_pipeline.accuracy import AccuracyConfig, AccuracyError, build_accuracy_package
from vid_pipeline.accuracy_judge import advise_disagreements
from vid_pipeline.accuracy_rebuild import rebuild_from_accuracy
from vid_pipeline.accuracy_review import build_accuracy_review
from vid_pipeline.editorial import EditorialConfig
from vid_pipeline.pre_review import PreReviewError, build_pre_review_package
from vid_pipeline.review import ReviewConfig, ReviewError, build_review_package
from vid_pipeline.standalone import VideoPipeline

_MAX_EDITORIAL_CHARS = 3500
_MAX_OUTPUT_TOKENS = 4500
_CONTEXT_WINDOW = 8192
_TIMEOUT_SECONDS = 900
_RETRIES = 2
_ORIGINAL_RUN_URL = base_cli.command_run_url


def reliable_editorial_config(args: Namespace) -> EditorialConfig:
    chunk_chars = max(2000, min(int(args.editorial_chunk_chars), _MAX_EDITORIAL_CHARS))
    max_output_tokens = max(
        1024,
        min(int(args.editorial_max_output_tokens), _MAX_OUTPUT_TOKENS),
    )
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


def _env_int(name: str, default: int) -> int:
    raw = os.getenv(name, "").strip()
    return int(raw) if raw else default


def _env_bool(name: str, default: bool = False) -> bool:
    raw = os.getenv(name, "").strip().lower()
    if not raw:
        return default
    return raw not in {"0", "false", "no", "off"}


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


def _accuracy_config(args: Namespace) -> AccuracyConfig:
    return AccuracyConfig(
        mode=os.getenv("VID_PIPELINE_ACCURACY_MODE", "balanced").strip()
        or "balanced",
        model=os.getenv("VID_PIPELINE_ACCURACY_MODEL", "").strip() or args.model,
        device=os.getenv("VID_PIPELINE_ACCURACY_DEVICE", "").strip()
        or args.device,
        compute_type=os.getenv("VID_PIPELINE_ACCURACY_COMPUTE_TYPE", "").strip()
        or args.compute_type,
        language=args.language,
        beam_size=_env_int(
            "VID_PIPELINE_ACCURACY_BEAM_SIZE",
            max(5, int(args.beam_size)),
        ),
        targeted_beam_size=_env_int("VID_PIPELINE_TARGETED_BEAM_SIZE", 10),
        clip_context_seconds=_env_float(
            "VID_PIPELINE_ACCURACY_CLIP_CONTEXT",
            2.5,
        ),
        max_targeted_segments=_env_int(
            "VID_PIPELINE_MAX_TARGETED_SEGMENTS",
            120,
        ),
        judge_model=os.getenv("VID_PIPELINE_ACCURACY_JUDGE_MODEL", "").strip(),
        judge_base_url=os.getenv(
            "OLLAMA_BASE_URL",
            "http://127.0.0.1:11434",
        ).strip(),
        whisperx_alignment=_env_bool(
            "VID_PIPELINE_WHISPERX_ALIGNMENT",
            False,
        ),
        whisperx_model=os.getenv("VID_PIPELINE_WHISPERX_MODEL", "").strip(),
        diarization=_env_bool("VID_PIPELINE_DIARIZATION", False),
        diarization_model=os.getenv(
            "VID_PIPELINE_DIARIZATION_MODEL",
            "pyannote/speaker-diarization-community-1",
        ).strip(),
        huggingface_token=os.getenv("HUGGINGFACE_TOKEN", "").strip(),
    )


def _review_config() -> ReviewConfig:
    return ReviewConfig(
        confidence_threshold=_env_float(
            "VID_PIPELINE_REVIEW_CONFIDENCE",
            0.68,
        ),
        segment_logprob_threshold=_env_float(
            "VID_PIPELINE_REVIEW_LOGPROB",
            -0.85,
        ),
        clip_context_seconds=_env_float(
            "VID_PIPELINE_REVIEW_CLIP_CONTEXT",
            3.0,
        ),
        extract_clips=_env_bool("VID_PIPELINE_REVIEW_CLIPS", True),
        retranscribe_model=os.getenv(
            "VID_PIPELINE_RETRANSCRIBE_MODEL",
            "",
        ).strip(),
        retranscribe_device=os.getenv(
            "VID_PIPELINE_RETRANSCRIBE_DEVICE",
            "cpu",
        ).strip(),
        retranscribe_compute_type=os.getenv(
            "VID_PIPELINE_RETRANSCRIBE_COMPUTE_TYPE",
            "int8",
        ).strip(),
    )


def _record_accuracy_failure(root: Path, error: Exception) -> None:
    result_path = root / "result.json"
    result = (
        json.loads(result_path.read_text(encoding="utf-8"))
        if result_path.exists()
        else {}
    )
    result.update(
        {
            "accuracy_status": "failed",
            "accuracy_error": f"{type(error).__name__}: {error}",
        }
    )
    result_path.write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def _run_url_with_review(args: Namespace) -> int:
    result = _ORIGINAL_RUN_URL(args)
    if result != 0:
        return result
    pipeline = VideoPipeline(args.url, args.output_root, args.name)
    glossaries = _default_glossaries()
    accuracy_manifest = None
    accuracy_judge = None
    accuracy_rebuild = None
    accuracy_review = None
    try:
        accuracy_config = _accuracy_config(args)
        accuracy_manifest = build_accuracy_package(
            pipeline.paths.job_root,
            config=accuracy_config,
            glossary_paths=glossaries,
        )
        accuracy_judge = advise_disagreements(
            pipeline.paths.job_root,
            model=accuracy_config.judge_model,
            base_url=accuracy_config.judge_base_url,
        )
        accuracy_review = build_accuracy_review(pipeline.paths.job_root)
        consensus_json = Path(accuracy_manifest["files"]["json"])
        editorial_config = (
            None if args.no_editorial else reliable_editorial_config(args)
        )
        editorial_metadata = base_cli._editorial_metadata(
            args,
            source_url=args.source_url.strip() or args.url,
        )
        accuracy_rebuild = rebuild_from_accuracy(
            pipeline.paths.job_root,
            consensus_json,
            title=args.title,
            source_url=args.source_url.strip() or args.url,
            max_words=args.max_paragraph_words,
            editorial_config=editorial_config,
            editorial_metadata=editorial_metadata,
        )
    except AccuracyError as exc:
        _record_accuracy_failure(pipeline.paths.job_root, exc)
        if _env_bool("VID_PIPELINE_ACCURACY_REQUIRED", False):
            print(f"error: accuracy stage failed: {exc}", file=sys.stderr)
            return 1
        print(
            f"warning: accuracy stage failed; original safe output retained: {exc}",
            file=sys.stderr,
        )
    try:
        pre_review = build_pre_review_package(pipeline.paths.job_root)
        review = build_review_package(
            pipeline.paths.job_root,
            config=_review_config(),
            glossary_paths=glossaries,
        )
    except (PreReviewError, ReviewError) as exc:
        print(f"error: review packaging failed: {exc}", file=sys.stderr)
        return 1
    print(
        json.dumps(
            {
                "accuracy_stage": accuracy_manifest,
                "accuracy_judge": accuracy_judge,
                "accuracy_review": accuracy_review,
                "accuracy_rebuild": accuracy_rebuild,
                "pre_review_stage": pre_review,
                "review_stage": review,
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


def main() -> int:
    base_cli._editorial_config = reliable_editorial_config
    base_cli.command_run_url = _run_url_with_review
    return base_cli.main()


if __name__ == "__main__":
    raise SystemExit(main())
