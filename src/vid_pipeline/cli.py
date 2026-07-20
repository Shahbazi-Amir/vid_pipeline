"""Command-line interface for the financial video RAG pipeline."""

from __future__ import annotations

import argparse
import json
import shutil
import sys
from pathlib import Path
from typing import Any

from vid_pipeline import __version__
from vid_pipeline.errors import PipelineError
from vid_pipeline.models import EpisodeSpec
from vid_pipeline.paths import EpisodePaths
from vid_pipeline.pipeline import EpisodePipeline
from vid_pipeline.publish import EXPECTED_BRANCH, publish_episode
from vid_pipeline.rag import build_rag, validate_jsonl
from vid_pipeline.review import mark_reviewed
from vid_pipeline.source import discover_site, save_candidates, validate_source
from vid_pipeline.state import PipelineState
from vid_pipeline.transcribe import DEFAULT_INITIAL_PROMPT, TranscriptionConfig


def _json_print(value: Any) -> None:
    print(json.dumps(value, ensure_ascii=False, indent=2))


def add_common_spec_argument(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("spec", type=Path, help="Path to the episode JSON specification.")
    parser.add_argument("--work-root", type=Path, default=Path("work"))


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="vid-pipeline",
        description="Process Persian financial education videos for review and RAG.",
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    subparsers = parser.add_subparsers(dest="command", required=True)

    init_parser = subparsers.add_parser("init", help="Create one episode specification.")
    init_parser.add_argument("output", type=Path)
    init_parser.add_argument("--program", required=True)
    init_parser.add_argument("--collection", required=True)
    init_parser.add_argument("--season", required=True)
    init_parser.add_argument("--season-episode", required=True, type=int)
    init_parser.add_argument("--overall-episode", required=True, type=int)
    init_parser.add_argument("--speaker", required=True)
    init_parser.add_argument("--title", default="")
    init_parser.add_argument("--input", dest="input_value", default="")
    init_parser.add_argument("--source-url", default="")
    init_parser.add_argument("--video-url", default="")
    init_parser.add_argument("--additional-speaker", action="append", default=[])
    init_parser.add_argument("--search-site", default="https://www.fintelligence.ir/")
    init_parser.add_argument("--source-verified", action="store_true")
    init_parser.add_argument("--speaker-verified", action="store_true")

    discover_parser = subparsers.add_parser(
        "discover", help="Search a site sitemap for source pages."
    )
    discover_parser.add_argument("--site", required=True)
    discover_parser.add_argument("--query", required=True)
    discover_parser.add_argument("--max-pages", type=int, default=30)
    discover_parser.add_argument("--output", type=Path, default=Path("candidates.json"))

    inspect_parser = subparsers.add_parser("inspect-source", help="Inspect a page or video URL.")
    inspect_parser.add_argument("url")
    inspect_parser.add_argument("--query", default="")

    run_parser = subparsers.add_parser(
        "run", help="Run automatic stages through review package."
    )
    add_common_spec_argument(run_parser)
    run_parser.add_argument("--model", default="small")
    run_parser.add_argument("--device", default="auto", choices=("auto", "cpu", "cuda"))
    run_parser.add_argument("--compute-type", default="auto")
    run_parser.add_argument("--beam-size", type=int, default=5)
    run_parser.add_argument("--initial-prompt", default=DEFAULT_INITIAL_PROMPT)
    run_parser.add_argument("--force", action="store_true")

    status_parser = subparsers.add_parser("status", help="Show persisted episode state.")
    add_common_spec_argument(status_parser)

    review_parser = subparsers.add_parser(
        "mark-reviewed", help="Record a completed audio review."
    )
    add_common_spec_argument(review_parser)
    review_parser.add_argument("--transcript", type=Path, required=True)
    review_parser.add_argument("--reviewer", required=True)
    review_parser.add_argument("--confirm-audio-reviewed", action="store_true")

    rag_parser = subparsers.add_parser("build-rag", help="Build reviewed JSONL chunks.")
    add_common_spec_argument(rag_parser)

    validate_parser = subparsers.add_parser("validate-rag", help="Validate a JSONL output.")
    validate_parser.add_argument("path", type=Path)

    publish_parser = subparsers.add_parser(
        "publish", help="Commit reviewed outputs to transcription repo."
    )
    add_common_spec_argument(publish_parser)
    publish_parser.add_argument("--destination-repo", type=Path, required=True)
    publish_parser.add_argument("--branch", default=EXPECTED_BRANCH)
    publish_parser.add_argument("--push", action="store_true")
    publish_parser.add_argument("--remote", default="origin")

    return parser


def command_init(args: argparse.Namespace) -> int:
    spec = EpisodeSpec(
        program=args.program,
        collection=args.collection,
        season=args.season,
        season_episode=args.season_episode,
        overall_episode=args.overall_episode,
        speaker=args.speaker,
        title=args.title,
        input_value=args.input_value,
        source_url=args.source_url,
        video_url=args.video_url,
        additional_speakers=args.additional_speaker,
        search_site=args.search_site,
        source_verified=args.source_verified,
        speaker_verified=args.speaker_verified,
    )
    spec.save(args.output)
    print(args.output)
    return 0


def command_discover(args: argparse.Namespace) -> int:
    candidates = discover_site(args.site, args.query, args.max_pages)
    save_candidates(candidates, args.output)
    _json_print([item.to_dict() for item in candidates[:10]])
    return 0 if candidates else 2


def command_inspect_source(args: argparse.Namespace) -> int:
    _json_print(validate_source(args.url, args.query).to_dict())
    return 0


def command_run(args: argparse.Namespace) -> int:
    spec = EpisodeSpec.load(args.spec)
    pipeline = EpisodePipeline(spec, args.work_root)
    config = TranscriptionConfig(
        model=args.model,
        device=args.device,
        compute_type=args.compute_type,
        beam_size=args.beam_size,
        initial_prompt=args.initial_prompt,
    )
    results = [pipeline.resolve_source(force=args.force)]
    spec.save(args.spec)
    results.extend(
        [
            pipeline.download(force=args.force),
            pipeline.audio(force=args.force),
            pipeline.transcribe(config=config, force=args.force),
            pipeline.review_package(force=args.force),
        ]
    )
    spec.save(args.spec)
    _json_print(results)
    print(f"Review file: {pipeline.paths.review_markdown}")
    return 0


def command_status(args: argparse.Namespace) -> int:
    spec = EpisodeSpec.load(args.spec)
    paths = EpisodePaths(args.work_root, spec)
    state = PipelineState(paths.state)
    _json_print(state.data)
    return 0


def command_mark_reviewed(args: argparse.Namespace) -> int:
    spec = EpisodeSpec.load(args.spec)
    paths = EpisodePaths(args.work_root, spec)
    paths.ensure()
    if args.transcript.resolve() != paths.final_markdown.resolve():
        shutil.copy2(args.transcript, paths.final_markdown)
    receipt = mark_reviewed(
        paths.audio,
        paths.final_markdown,
        paths.review_receipt,
        args.reviewer,
        args.confirm_audio_reviewed,
    )
    state = PipelineState(paths.state)
    state.mark_complete(
        "review",
        [paths.final_markdown, receipt],
        {"reviewer": args.reviewer},
        status="reviewed",
    )
    print(paths.final_markdown)
    return 0


def command_build_rag(args: argparse.Namespace) -> int:
    spec = EpisodeSpec.load(args.spec)
    paths = EpisodePaths(args.work_root, spec)
    records = build_rag(
        spec, paths.final_markdown, paths.review_receipt, paths.rag_jsonl
    )
    state = PipelineState(paths.state)
    state.mark_complete("rag", [paths.rag_jsonl], {"chunks": len(records)})
    print(f"{paths.rag_jsonl} ({len(records)} chunks)")
    return 0


def command_publish(args: argparse.Namespace) -> int:
    spec = EpisodeSpec.load(args.spec)
    sha = publish_episode(
        spec,
        args.work_root,
        args.destination_repo,
        expected_branch=args.branch,
        push=args.push,
        remote=args.remote,
    )
    print(sha)
    return 0


def command_validate_rag(args: argparse.Namespace) -> int:
    print(validate_jsonl(args.path))
    return 0


def dispatch(args: argparse.Namespace) -> int:
    commands = {
        "init": command_init,
        "discover": command_discover,
        "inspect-source": command_inspect_source,
        "run": command_run,
        "status": command_status,
        "mark-reviewed": command_mark_reviewed,
        "build-rag": command_build_rag,
        "validate-rag": command_validate_rag,
        "publish": command_publish,
    }
    return commands[args.command](args)


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    try:
        return dispatch(args)
    except (PipelineError, ValueError, OSError, json.JSONDecodeError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
