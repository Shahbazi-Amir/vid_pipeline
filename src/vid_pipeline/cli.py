"""Command-line interface for the standalone video-to-text pipeline."""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any

from vid_pipeline import __version__
from vid_pipeline.clean import clean_transcript
from vid_pipeline.download import extract_metadata
from vid_pipeline.editorial import EditorialConfig, EditorialMetadata, edit_transcript
from vid_pipeline.errors import PipelineError
from vid_pipeline.standalone import LocalMediaPipeline, VideoPipeline
from vid_pipeline.transcribe import DEFAULT_INITIAL_PROMPT, TranscriptionConfig


def _json_print(value: Any) -> None:
    print(json.dumps(value, ensure_ascii=False, indent=2))


def _add_transcription_options(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--model", default="large-v3-turbo")
    parser.add_argument("--device", default="auto", choices=("auto", "cpu", "cuda"))
    parser.add_argument("--compute-type", default="auto")
    parser.add_argument("--language", default="fa")
    parser.add_argument("--beam-size", type=int, default=5)
    parser.add_argument("--initial-prompt", default=DEFAULT_INITIAL_PROMPT)
    parser.add_argument("--hotwords", default="")


def _add_editorial_metadata_options(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--title", default="")
    parser.add_argument("--program", default="")
    parser.add_argument("--network", default="")
    parser.add_argument("--date", default="")
    parser.add_argument("--guest", default="")
    parser.add_argument("--duration", default="")
    parser.add_argument("--speaker", action="append", default=[])
    parser.add_argument("--editorial-context", default="")


def _editorial_metadata(args: argparse.Namespace, *, source_url: str) -> EditorialMetadata:
    return EditorialMetadata(
        title=args.title,
        source_url=source_url,
        program=args.program,
        network=args.network,
        date=args.date,
        guest=args.guest,
        duration=args.duration,
        speakers=list(args.speaker),
        context=args.editorial_context,
    )


def _editorial_config(args: argparse.Namespace) -> EditorialConfig:
    return EditorialConfig(
        model=args.editorial_model,
        base_url=args.editorial_base_url,
        chunk_chars=args.editorial_chunk_chars,
        max_output_tokens=args.editorial_max_output_tokens,
    )


def _add_editorial_options(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--no-editorial", action="store_true")
    parser.add_argument(
        "--editorial-model",
        default=os.getenv("VID_PIPELINE_EDITORIAL_MODEL", "qwen3:8b"),
    )
    parser.add_argument(
        "--editorial-base-url",
        default=os.getenv("OLLAMA_BASE_URL", "http://127.0.0.1:11434"),
    )
    parser.add_argument("--editorial-chunk-chars", type=int, default=7000)
    parser.add_argument("--editorial-max-output-tokens", type=int, default=12000)
    _add_editorial_metadata_options(parser)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="vid-pipeline",
        description="Convert a video URL into raw, machine-cleaned, and locally edited transcripts.",
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    subparsers = parser.add_subparsers(dest="command", required=True)

    run_parser = subparsers.add_parser(
        "run-url",
        help="Download one video URL and create reviewed Markdown and plain-text transcripts.",
    )
    run_parser.add_argument("url")
    run_parser.add_argument("--source-url", default="")
    run_parser.add_argument("--output-root", type=Path, default=Path("outputs"))
    run_parser.add_argument("--name", default="")
    run_parser.add_argument("--max-paragraph-words", type=int, default=90)
    run_parser.add_argument("--force", action="store_true")
    _add_transcription_options(run_parser)
    _add_editorial_options(run_parser)

    file_parser = subparsers.add_parser("run-file", help="Process one local media file.")
    file_parser.add_argument("path", type=Path)
    file_parser.add_argument("--output-root", type=Path, default=Path("outputs"))
    file_parser.add_argument("--name", default="")
    file_parser.add_argument("--max-paragraph-words", type=int, default=90)
    file_parser.add_argument("--force", action="store_true")
    file_parser.add_argument("--resume", action="store_true")
    file_parser.add_argument("--profile", choices=("fast", "balanced", "accurate"), default="balanced")
    _add_transcription_options(file_parser)
    _add_editorial_options(file_parser)

    folder_parser = subparsers.add_parser("run-folder", help="Process local media files as jobs.")
    folder_parser.add_argument("path", type=Path)
    folder_parser.add_argument("--recursive", action="store_true")
    folder_parser.add_argument("--output-root", type=Path, default=Path("outputs"))
    folder_parser.add_argument("--workers", type=int, default=1)
    folder_parser.add_argument("--extensions", default="")
    folder_parser.add_argument("--force", action="store_true")
    folder_parser.add_argument("--resume", action="store_true")
    folder_parser.add_argument("--profile", choices=("fast", "balanced", "accurate"), default="balanced")
    folder_parser.add_argument("--model", default="small")
    folder_parser.add_argument("--language", default="fa")
    folder_parser.add_argument("--editorial-model", default=os.getenv("VID_PIPELINE_EDITORIAL_MODEL", "qwen3:8b"))
    folder_parser.add_argument("--no-editorial", action="store_true")

    inspect_parser = subparsers.add_parser("inspect", help="Inspect a video URL with yt-dlp.")
    inspect_parser.add_argument("url")

    clean_parser = subparsers.add_parser(
        "clean",
        help="Create machine-cleaned transcript files from an existing Whisper JSON file.",
    )
    clean_parser.add_argument("raw_json", type=Path)
    clean_parser.add_argument("--markdown", type=Path, required=True)
    clean_parser.add_argument("--text", type=Path, required=True)
    clean_parser.add_argument("--title", default="")
    clean_parser.add_argument("--source-url", default="")
    clean_parser.add_argument("--max-paragraph-words", type=int, default=90)

    edit_parser = subparsers.add_parser(
        "edit",
        help="Create locally edited final files from an existing Whisper JSON file.",
    )
    edit_parser.add_argument("raw_json", type=Path)
    edit_parser.add_argument("--markdown", type=Path, required=True)
    edit_parser.add_argument("--text", type=Path, required=True)
    edit_parser.add_argument("--source-url", default="")
    edit_parser.add_argument(
        "--editorial-model",
        default=os.getenv("VID_PIPELINE_EDITORIAL_MODEL", "qwen3:8b"),
    )
    edit_parser.add_argument(
        "--editorial-base-url",
        default=os.getenv("OLLAMA_BASE_URL", "http://127.0.0.1:11434"),
    )
    edit_parser.add_argument("--editorial-chunk-chars", type=int, default=7000)
    edit_parser.add_argument("--editorial-max-output-tokens", type=int, default=12000)
    _add_editorial_metadata_options(edit_parser)

    status_parser = subparsers.add_parser("status", help="Show the saved state for one job.")
    status_parser.add_argument("job_id")
    status_parser.add_argument("--output-root", type=Path, default=Path("outputs"))

    return parser


def command_run_url(args: argparse.Namespace) -> int:
    pipeline = VideoPipeline(args.url, args.output_root, args.name)
    hints = [args.title, args.guest, *list(args.speaker), args.editorial_context]
    hint_text = "، ".join(item.strip() for item in hints if item and item.strip())
    initial_prompt = args.initial_prompt.strip() or "رونویسی دقیق یک سخنرانی رسمی فارسی."
    if hint_text:
        initial_prompt = f"{initial_prompt} {hint_text}"[:220]
    hotwords = args.hotwords.strip()
    if not hotwords:
        hotwords = "، ".join(
            item.strip()
            for item in [args.title, args.guest, *list(args.speaker), args.editorial_context]
            if item and item.strip()
        )
    hotwords = hotwords[:240]
    config = TranscriptionConfig(
        model=args.model,
        device=args.device,
        compute_type=args.compute_type,
        language=args.language,
        beam_size=args.beam_size,
        condition_on_previous_text=False,
        initial_prompt=initial_prompt,
        hotwords=hotwords,
        repetition_penalty=1.08,
        no_repeat_ngram_size=3,
        hallucination_silence_threshold=2.0,
    )
    editorial_config = None if args.no_editorial else _editorial_config(args)
    results = pipeline.run(
        config,
        editorial_config=editorial_config,
        editorial_metadata=_editorial_metadata(
            args,
            source_url=args.source_url.strip() or args.url,
        ),
        max_words=args.max_paragraph_words,
        force=args.force,
    )
    _json_print(
        {
            "job_id": pipeline.job_id,
            "job_root": str(pipeline.paths.job_root),
            "raw_markdown": str(pipeline.paths.raw_markdown),
            "machine_markdown": str(pipeline.paths.machine_markdown),
            "final_markdown": str(pipeline.paths.final_markdown),
            "final_text": str(pipeline.paths.final_text),
            "stages": results,
        }
    )
    return 0


def _transcription_config(args: argparse.Namespace) -> TranscriptionConfig:
    return TranscriptionConfig(
        model=args.model,
        device=args.device,
        compute_type=args.compute_type,
        language=args.language,
        beam_size=args.beam_size,
        initial_prompt=args.initial_prompt,
        hotwords=args.hotwords,
    )


def command_run_file(args: argparse.Namespace) -> int:
    pipeline = LocalMediaPipeline(args.path, args.output_root, args.name)
    results = pipeline.run(
        _transcription_config(args),
        editorial_config=None if args.no_editorial else _editorial_config(args),
        editorial_metadata=_editorial_metadata(args, source_url=""),
        max_words=args.max_paragraph_words,
        force=args.force,
    )
    _json_print({"job_id": pipeline.job_id, "job_root": str(pipeline.paths.job_root), "stages": results})
    return 0


_MEDIA_EXTENSIONS = {
    ".mp4", ".mkv", ".mov", ".webm", ".m4v", ".avi",
    ".mp3", ".wav", ".m4a", ".flac", ".ogg",
}


def command_run_folder(args: argparse.Namespace) -> int:
    if not args.path.is_dir():
        raise ValueError(f"media folder does not exist: {args.path}")
    extensions = {
        item if item.startswith(".") else f".{item}"
        for item in args.extensions.lower().split(",")
        if item.strip()
    } or _MEDIA_EXTENSIONS
    iterator = args.path.rglob("*") if args.recursive else args.path.glob("*")
    files = sorted(path for path in iterator if path.is_file() and path.suffix.lower() in extensions)
    summary: dict[str, Any] = {"total": len(files), "successful": 0, "failed": 0, "skipped": 0, "files": []}
    for path in files:
        values = {
            **vars(args),
            "path": path,
            "name": "",
            "device": "auto",
            "compute_type": "auto",
            "beam_size": 5,
            "initial_prompt": DEFAULT_INITIAL_PROMPT,
            "hotwords": "",
            "max_paragraph_words": 90,
            "editorial_base_url": os.getenv("OLLAMA_BASE_URL", "http://127.0.0.1:11434"),
            "editorial_chunk_chars": 7000,
            "editorial_max_output_tokens": 12000,
            "title": "",
            "program": "",
            "network": "",
            "date": "",
            "guest": "",
            "duration": "",
            "speaker": [],
            "editorial_context": "",
        }
        namespace = argparse.Namespace(**values)
        try:
            command_run_file(namespace)
            summary["successful"] += 1
            summary["files"].append({"path": str(path), "status": "completed"})
        except Exception as exc:
            summary["failed"] += 1
            summary["files"].append({"path": str(path), "status": "failed", "error": str(exc)})
    _json_print(summary)
    return 1 if summary["failed"] else 0


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


def command_edit(args: argparse.Namespace) -> int:
    result = edit_transcript(
        args.raw_json,
        args.markdown,
        args.text,
        metadata=_editorial_metadata(args, source_url=args.source_url),
        config=_editorial_config(args),
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
        "run-file": command_run_file,
        "run-folder": command_run_folder,
        "inspect": command_inspect,
        "clean": command_clean,
        "edit": command_edit,
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
