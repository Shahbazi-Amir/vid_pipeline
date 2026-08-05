"""Command line interface for pre-review, AI review, and auditable human review."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from vid_pipeline.llm_review import AIReviewError, review_collection_output
from vid_pipeline.pre_review import PreReviewError, build_pre_review_package
from vid_pipeline.review import (
    ReviewConfig,
    ReviewError,
    apply_human_review,
    build_review_package,
)


def _print(value: object) -> None:
    print(json.dumps(value, ensure_ascii=False, indent=2))


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="vid-review",
        description="Build automated, pre-review, and auditable human-review outputs.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    ai_collection = subparsers.add_parser(
        "ai-collection",
        help="Review one numbered collection transcript through the configured LLM API.",
    )
    ai_collection.add_argument("collection_root", type=Path)
    ai_collection.add_argument("result_number", type=int)
    ai_collection.add_argument(
        "--force",
        action="store_true",
        help="Run the API again even when a reviewed timestamped file already exists.",
    )

    pre_review = subparsers.add_parser(
        "pre-review",
        help="Create the complete time-aligned transcript before any review.",
    )
    pre_review.add_argument("job_root", type=Path)

    build = subparsers.add_parser(
        "build",
        help="Create pre-review files, uncertain spans, clips, audit and HTML UI.",
    )
    build.add_argument("job_root", type=Path)
    build.add_argument("--glossary", action="append", type=Path, default=[])
    build.add_argument("--confidence-threshold", type=float, default=0.68)
    build.add_argument("--segment-logprob-threshold", type=float, default=-0.85)
    build.add_argument("--clip-context-seconds", type=float, default=3.0)
    build.add_argument("--no-clips", action="store_true")
    build.add_argument("--retranscribe-model", default="")
    build.add_argument("--device", default="cpu", choices=("auto", "cpu", "cuda"))
    build.add_argument("--compute-type", default="int8")
    build.add_argument("--retranscribe-beam-size", type=int, default=8)

    apply = subparsers.add_parser("apply", help="Apply completed corrections and verify/promote.")
    apply.add_argument("job_root", type=Path)
    apply.add_argument("corrections", type=Path)
    apply.add_argument("--reviewer", default="")
    apply.add_argument("--promote", action="store_true")
    apply.add_argument("--paragraph-words", type=int, default=90)

    status = subparsers.add_parser("status", help="Show pre-review, review or verification status.")
    status.add_argument("job_root", type=Path)
    return parser


def main() -> int:
    args = build_parser().parse_args()
    try:
        if args.command == "ai-collection":
            _print(
                review_collection_output(
                    args.collection_root,
                    args.result_number,
                    force=args.force,
                )
            )
            return 0
        if args.command == "pre-review":
            _print(build_pre_review_package(args.job_root))
            return 0
        if args.command == "build":
            config = ReviewConfig(
                confidence_threshold=args.confidence_threshold,
                segment_logprob_threshold=args.segment_logprob_threshold,
                clip_context_seconds=args.clip_context_seconds,
                extract_clips=not args.no_clips,
                retranscribe_model=args.retranscribe_model,
                retranscribe_device=args.device,
                retranscribe_compute_type=args.compute_type,
                retranscribe_beam_size=args.retranscribe_beam_size,
            )
            pre_review = build_pre_review_package(args.job_root)
            review = build_review_package(
                args.job_root,
                config=config,
                glossary_paths=args.glossary,
            )
            _print({"pre_review_stage": pre_review, "review_stage": review})
            return 0
        if args.command == "apply":
            _print(
                apply_human_review(
                    args.job_root,
                    args.corrections,
                    reviewer=args.reviewer,
                    promote=args.promote,
                    paragraph_words=args.paragraph_words,
                )
            )
            return 0
        verification = args.job_root / "human" / "verification.json"
        manifest = args.job_root / "review" / "manifest.json"
        pre_review_manifest = args.job_root / "pre_review" / "manifest.json"
        selected = (
            verification
            if verification.exists()
            else manifest
            if manifest.exists()
            else pre_review_manifest
        )
        if not selected.exists():
            raise ReviewError("No pre-review, review or human verification exists for this job.")
        _print(json.loads(selected.read_text(encoding="utf-8")))
        return 0
    except (
        AIReviewError,
        PreReviewError,
        ReviewError,
        OSError,
        ValueError,
        json.JSONDecodeError,
    ) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
