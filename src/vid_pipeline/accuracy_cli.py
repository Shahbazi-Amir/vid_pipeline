"""Command line interface for multi-pass ASR accuracy."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from vid_pipeline.accuracy import (
    AccuracyConfig,
    AccuracyError,
    build_accuracy_package,
    evaluate_corpus,
    evaluate_files,
)
from vid_pipeline.accuracy_review import (
    apply_accuracy_review,
    build_accuracy_review,
    update_learned_glossary,
)


def output(value: object) -> None:
    print(json.dumps(value, ensure_ascii=False, indent=2))


def parser() -> argparse.ArgumentParser:
    root = argparse.ArgumentParser(prog="vid-accuracy")
    commands = root.add_subparsers(dest="command", required=True)
    build = commands.add_parser("build")
    build.add_argument("job_root", type=Path)
    build.add_argument(
        "--mode",
        choices=("off", "fast", "balanced", "maximum"),
        default="balanced",
    )
    build.add_argument("--model", default="")
    build.add_argument("--device", choices=("auto", "cpu", "cuda"), default="auto")
    build.add_argument("--compute-type", default="auto")
    build.add_argument("--glossary", action="append", type=Path, default=[])
    build.add_argument("--whisperx", action="store_true")
    build.add_argument("--whisperx-model", default="")
    build.add_argument("--diarize", action="store_true")
    build.add_argument("--diarization-cache-dir", type=Path)
    review = commands.add_parser("review")
    review.add_argument("job_root", type=Path)
    apply = commands.add_parser("apply-review")
    apply.add_argument("job_root", type=Path)
    apply.add_argument("corrections", type=Path)
    apply.add_argument("--reviewer", default="")
    evaluate = commands.add_parser("evaluate")
    evaluate.add_argument("reference", type=Path)
    evaluate.add_argument("hypothesis", type=Path)
    evaluate.add_argument("--output", type=Path)
    corpus = commands.add_parser("evaluate-corpus")
    corpus.add_argument("manifest", type=Path)
    corpus.add_argument("--output", type=Path)
    learn = commands.add_parser("learn-glossary")
    learn.add_argument("job_root", type=Path)
    learn.add_argument("corrections", type=Path)
    learn.add_argument("--output", type=Path)
    return root


def main() -> int:
    args = parser().parse_args()
    try:
        if args.command == "build":
            config = AccuracyConfig(
                mode=args.mode,
                model=args.model,
                device=args.device,
                compute_type=args.compute_type,
                whisperx_alignment=args.whisperx,
                whisperx_model=args.whisperx_model,
                diarization=args.diarize,
                diarization_cache_dir=args.diarization_cache_dir,
            )
            output(
                build_accuracy_package(
                    args.job_root,
                    config=config,
                    glossary_paths=args.glossary,
                )
            )
        elif args.command == "review":
            output(build_accuracy_review(args.job_root))
        elif args.command == "apply-review":
            output(
                apply_accuracy_review(
                    args.job_root,
                    args.corrections,
                    reviewer=args.reviewer,
                )
            )
        elif args.command == "evaluate":
            output(evaluate_files(args.reference, args.hypothesis, args.output))
        elif args.command == "evaluate-corpus":
            output(evaluate_corpus(args.manifest, args.output))
        else:
            output(
                update_learned_glossary(
                    args.job_root,
                    args.corrections,
                    args.output,
                )
            )
        return 0
    except (AccuracyError, OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
