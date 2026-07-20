"""Build and validate JSONL chunks compatible with the destination repository."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from vid_pipeline.models import EpisodeSpec
from vid_pipeline.review import verify_review


def sections(markdown: str) -> list[str]:
    markdown = re.sub(r"^# .+?\n", "", markdown, count=1)
    markdown = re.sub(r"^>.*?\n", "", markdown, flags=re.MULTILINE)
    parts = re.split(r"(?=^##+ )", markdown, flags=re.MULTILINE)
    return [
        re.sub(r"\n{3,}", "\n\n", part).strip()
        for part in parts
        if len(part.strip()) > 80
    ]


def split_long(text: str, limit: int = 1800) -> list[str]:
    if len(text) <= limit:
        return [text]
    paragraphs = text.split("\n\n")
    chunks: list[str] = []
    current: list[str] = []
    for paragraph in paragraphs:
        proposal = "\n\n".join([*current, paragraph])
        if current and len(proposal) > limit:
            chunks.append("\n\n".join(current))
            current = [paragraph]
        else:
            current.append(paragraph)
    if current:
        chunks.append("\n\n".join(current))
    return chunks


def build_rag(
    spec: EpisodeSpec,
    final_transcript: str | Path,
    review_receipt: str | Path,
    destination: str | Path,
) -> list[dict[str, Any]]:
    verify_review(final_transcript, review_receipt)
    markdown = Path(final_transcript).read_text(encoding="utf-8")
    chunks = [chunk for section in sections(markdown) for chunk in split_long(section)]
    records: list[dict[str, Any]] = []
    for index, text in enumerate(chunks, 1):
        records.append(
            {
                "id": f"{spec.record_id}-{index:03d}",
                "text": text,
                "metadata": {
                    "program": spec.program,
                    "season": spec.season,
                    "episode": spec.season_episode,
                    "overall_episode": spec.overall_episode,
                    "title": spec.title,
                    "speakers": spec.speakers,
                    "source_url": spec.source_url,
                    "video_url": spec.video_url,
                    "language": "fa",
                    "review_status": "reviewed",
                },
            }
        )
    validate_records(records)
    path = Path(destination)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "".join(json.dumps(record, ensure_ascii=False) + "\n" for record in records),
        encoding="utf-8",
    )
    return records


def validate_records(records: list[dict[str, Any]]) -> None:
    if not records:
        raise ValueError("RAG output contains no chunks.")
    seen: set[str] = set()
    for record in records:
        if not record.get("id") or record["id"] in seen:
            raise ValueError("RAG record IDs must be unique and non-empty.")
        seen.add(record["id"])
        if not str(record.get("text", "")).strip():
            raise ValueError(f"Empty text in {record['id']}")
        metadata = record.get("metadata") or {}
        required = {
            "program",
            "episode",
            "title",
            "speakers",
            "source_url",
            "review_status",
        }
        missing = required - metadata.keys()
        if missing:
            raise ValueError(f"Missing metadata in {record['id']}: {sorted(missing)}")
        if metadata.get("review_status") != "reviewed":
            raise ValueError("Only reviewed records may be exported.")


def validate_jsonl(path: str | Path) -> int:
    records = [
        json.loads(line)
        for line in Path(path).read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    validate_records(records)
    return len(records)
