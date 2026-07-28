#!/usr/bin/env python3
"""Transcribe one audio chunk or merge chunk transcripts."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any

from vid_pipeline.transcribe import TranscriptionConfig, format_timestamp, transcribe_audio

_CHUNK_RE = re.compile(r"chunk-(\d+)")


def _chunk_index(path: Path) -> int:
    match = _CHUNK_RE.search(path.stem)
    if not match:
        raise ValueError(f"Chunk filename must contain chunk-NNN: {path}")
    return int(match.group(1))


def transcribe_chunk(args: argparse.Namespace) -> None:
    source = Path(args.audio)
    index = _chunk_index(source)
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    markdown = output.with_suffix(".md")
    result = transcribe_audio(
        source,
        output,
        markdown,
        TranscriptionConfig(
            model=args.model,
            device="cpu",
            compute_type="int8",
            language=args.language,
            beam_size=args.beam_size,
            condition_on_previous_text=False,
            initial_prompt=args.initial_prompt,
            hotwords=args.hotwords,
            repetition_penalty=1.08,
            no_repeat_ngram_size=3,
            hallucination_silence_threshold=2.0,
            log_progress=True,
        ),
    )
    result["chunk_index"] = index
    result["chunk_offset"] = index * args.chunk_seconds
    output.write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def _offset_segment(segment: dict[str, Any], offset: float, segment_id: int) -> dict[str, Any]:
    adjusted = dict(segment)
    adjusted["id"] = segment_id
    adjusted["start"] = float(segment.get("start", 0.0)) + offset
    adjusted["end"] = float(segment.get("end", 0.0)) + offset
    adjusted["words"] = [
        {
            **word,
            "start": float(word.get("start", 0.0)) + offset,
            "end": float(word.get("end", 0.0)) + offset,
        }
        for word in segment.get("words") or []
    ]
    return adjusted


def merge_chunks(args: argparse.Namespace) -> None:
    files = sorted(Path(args.input_dir).glob("**/chunk-*.json"), key=_chunk_index)
    if not files:
        raise ValueError("No chunk transcripts were found.")
    indexes = [_chunk_index(path) for path in files]
    expected = list(range(indexes[-1] + 1))
    if indexes != expected:
        raise ValueError(f"Missing or duplicate chunks: expected {expected}, got {indexes}")

    segments: list[dict[str, Any]] = []
    texts: list[str] = []
    model = ""
    language = args.language
    for path in files:
        data = json.loads(path.read_text(encoding="utf-8"))
        offset = float(data.get("chunk_offset", _chunk_index(path) * args.chunk_seconds))
        model = model or str(data.get("model", ""))
        language = str(data.get("language", language))
        for segment in data.get("segments") or []:
            adjusted = _offset_segment(segment, offset, len(segments))
            segments.append(adjusted)
            if adjusted.get("text"):
                texts.append(str(adjusted["text"]).strip())

    result = {
        "schema_version": 1,
        "language": language,
        "language_probability": 1.0,
        "duration": max((float(item["end"]) for item in segments), default=0.0),
        "model": model,
        "device": "cpu",
        "compute_type": "int8",
        "text": " ".join(texts).strip(),
        "segments": segments,
        "chunk_count": len(files),
    }
    output = Path(args.output_json)
    markdown = Path(args.output_markdown)
    output.parent.mkdir(parents=True, exist_ok=True)
    markdown.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    lines = ["# متن خام زمان‌دار", ""]
    for segment in segments:
        lines.extend(
            [
                f"[{format_timestamp(segment['start'])} → {format_timestamp(segment['end'])}]",
                str(segment.get("text") or "[نامفهوم]"),
                "",
            ]
        )
    markdown.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")


def parser() -> argparse.ArgumentParser:
    root = argparse.ArgumentParser()
    commands = root.add_subparsers(dest="command", required=True)
    transcribe = commands.add_parser("transcribe")
    transcribe.add_argument("audio")
    transcribe.add_argument("--output", required=True)
    transcribe.add_argument("--model", default="large-v3-turbo")
    transcribe.add_argument("--language", default="fa")
    transcribe.add_argument("--beam-size", type=int, default=3)
    transcribe.add_argument("--chunk-seconds", type=int, default=600)
    transcribe.add_argument("--initial-prompt", default="")
    transcribe.add_argument("--hotwords", default="")
    transcribe.set_defaults(handler=transcribe_chunk)
    merge = commands.add_parser("merge")
    merge.add_argument("input_dir")
    merge.add_argument("--output-json", required=True)
    merge.add_argument("--output-markdown", required=True)
    merge.add_argument("--language", default="fa")
    merge.add_argument("--chunk-seconds", type=int, default=600)
    merge.set_defaults(handler=merge_chunks)
    return root


def main() -> None:
    args = parser().parse_args()
    args.handler(args)


if __name__ == "__main__":
    main()
