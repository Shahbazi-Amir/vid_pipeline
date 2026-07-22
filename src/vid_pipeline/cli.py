"""Command-line interface for the standalone video-to-text pipeline."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from vid_pipeline import __version__
from vid_pipeline.clean import clean_transcript
from vid_pipeline.download import extract_metadata
from vid_pipeline.errors import PipelineError
from vid_pipeline.standalone import VideoPipeline
from vid_pipeline.transcribe import DEFAULT_INITIAL_PROMPT, TranscriptionConfig


def _json_print(value: Any) -> None:
    print(json.dumps(value, ensure_ascii=False, indent=2))


def _add_transcription_options(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--model", default="small")
    parser.add_argument("--device", default="auto", choices=("auto", "cpu", "cuda"))
    parser.add_argument("--compute-type", default="auto")
    parser.add_argument("--language", default="fa")
    parser.add_argument("--beam-size", type=int, default=5)
    parser.add_argument("--initial-prompt", default=DEFAULT_INITIAL_PROMPT)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="vid-pipeline",
        description="Convert a video URL into raw and machine-cleaned transcript files.",
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    subparsers = parser.add_subparsers(dest="command", required=True)

    run_parser = subparsers.add_parser(
        "run-url",
        help="Download one video URL and create final Markdown and plain-text transcripts.",
    )
    run_parser.add_argument("url")
    run_parser.add_argument("--output-root", type=Path, default=Path("outputs"))
    run_parser.add_argument("--name", default="")
    run_parser.add_argument("--max-paragraph-words", type=int, default=90)
    run_parser.add_argument("--force", action="store_true")
    _add_transcription_options(run_parser)

    inspect_parser = subparsers.add_parser("inspect", help="Inspect a video URL with yt-dlp.")
    inspect_parser.add_argument("url")

    clean_parser = subparsers.add_parser(
        "clean",
        help="Create final transcript files from an existing Whisper JSON file.",
    )
    clean_parser.add_argument("raw_json", type=Path)
    clean_parser.add_argument("--markdown", type=Path, required=True)
    clean_parser.add_argument("--text", type=Path, required=True)
    clean_parser.add_argument("--title", default="")
    clean_parser.add_argument("--source-url", default="")
    clean_parser.add_argument("--max-paragraph-words", type=int, default=90)

    status_parser = subparsers.add_parser("status", help="Show the saved state for one job.")
    status_parser.add_argument("job_id")
    status_parser.add_argument("--output-root", type=Path, default=Path("outputs"))

    return parser


def command_run_url(args: argparse.Namespace) -> int:
    pipeline = VideoPipeline(args.url, args.output_root, args.name)
    config = TranscriptionConfig(
        model=args.model,
        device=args.device,
        compute_type=args.compute_type,
        language=args.language,
        beam_size=args.beam_size,
        initial_prompt=args.initial_prompt,
    )
    results = pipeline.run(
        config,
        max_words=args.max_paragraph_words,
        force=args.force,
    )
    _json_print(
        {
            "job_id": pipeline.job_id,
            "job_root": str(pipeline.paths.job_root),
            "final_markdown": str(pipeline.paths.final_markdown),
            "final_text": str(pipeline.paths.final_text),
            "stages": results,
        }
    )
    return 0


def command_inspect(args: argparse.Namespace) -> int:
    _json_print(extract_metadata(args.url))
    return 0


def command_clean(args: argparse.Namespace) -> int:
    result = clean_transcript(
        args.raw_json,
        args.markdown,
        args.text,
        title=args.title,
        source_url=args.source_url,
        max_words=args.max_paragraph_words,
    )
    _json_print(result)
    return 0


def command_status(args: argparse.Namespace) -> int:
    state_path = args.output_root / args.job_id / "state.json"
    if not state_path.exists():
        raise PipelineError(f"Job state does not exist: {state_path}")
    _json_print(json.loads(state_path.read_text(encoding="utf-8")))
    return 0


def dispatch(args: argparse.Namespace) -> int:
    commands = {
        "run-url": command_run_url,
        "inspect": command_inspect,
        "clean": command_clean,
        "status": command_status,
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
