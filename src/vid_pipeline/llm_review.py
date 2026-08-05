"""LLM-backed, validated review for numbered transcript collections."""

from __future__ import annotations

import json
import os
import re
import socket
import time
import urllib.error
import urllib.request
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from vid_pipeline.review_prompt import PERSIAN_TRANSCRIPT_REVIEW_PROMPT

_REVIEW_ENV = (
    "VID_PIPELINE_REVIEW_API_KEY",
    "VID_PIPELINE_REVIEW_BASE_URL",
    "VID_PIPELINE_REVIEW_MODEL",
)

_HEADER_RE = re.compile(
    r"(?m)^(?P<timestamp>\[\d{2}:\d{2}:\d{2} → \d{2}:\d{2}:\d{2}\]) "
    r"\*\*(?P<speaker>[^\r\n*]+)\*\*\s*$"
)


class AIReviewError(RuntimeError):
    """Raised when an automated transcript review cannot be trusted or completed."""


@dataclass(frozen=True)
class ReviewAPIConfig:
    api_key: str
    base_url: str
    model: str
    timeout_seconds: float = 900.0
    max_attempts: int = 4

    @classmethod
    def from_env(cls) -> "ReviewAPIConfig":
        values = {name: os.environ.get(name, "").strip() for name in _REVIEW_ENV}
        missing = [name for name, value in values.items() if not value]
        if missing:
            raise AIReviewError(
                "review API configuration is incomplete: " + ", ".join(missing)
            )
        try:
            timeout = float(os.environ.get("VID_PIPELINE_REVIEW_TIMEOUT_SECONDS", "900"))
            attempts = int(os.environ.get("VID_PIPELINE_REVIEW_MAX_ATTEMPTS", "4"))
        except ValueError as exc:
            raise AIReviewError("invalid review timeout or retry configuration") from exc
        if timeout <= 0 or attempts < 1:
            raise AIReviewError("review timeout must be positive and attempts must be at least 1")
        return cls(
            api_key=values["VID_PIPELINE_REVIEW_API_KEY"],
            base_url=values["VID_PIPELINE_REVIEW_BASE_URL"].rstrip("/"),
            model=values["VID_PIPELINE_REVIEW_MODEL"],
            timeout_seconds=timeout,
            max_attempts=attempts,
        )


@dataclass(frozen=True)
class TranscriptBlock:
    timestamp: str
    speaker: str
    text: str


def review_is_configured() -> bool:
    return all(os.environ.get(name, "").strip() for name in _REVIEW_ENV)


def _extract_blocks(text: str) -> list[TranscriptBlock]:
    matches = list(_HEADER_RE.finditer(text))
    blocks: list[TranscriptBlock] = []
    for index, match in enumerate(matches):
        end = matches[index + 1].start() if index + 1 < len(matches) else len(text)
        body = text[match.end() : end].strip()
        blocks.append(
            TranscriptBlock(
                timestamp=match.group("timestamp"),
                speaker=match.group("speaker").strip(),
                text=body,
            )
        )
    return blocks


def _strip_optional_code_fence(text: str) -> str:
    cleaned = text.strip()
    if not cleaned.startswith("```"):
        return cleaned
    lines = cleaned.splitlines()
    if len(lines) >= 3 and lines[-1].strip() == "```":
        return "\n".join(lines[1:-1]).strip()
    return cleaned


def validate_review(source: str, reviewed: str) -> list[TranscriptBlock]:
    source_blocks = _extract_blocks(source)
    reviewed_blocks = _extract_blocks(reviewed)
    if not source_blocks:
        raise AIReviewError("source transcript has no timestamped speaker blocks")
    if len(reviewed_blocks) != len(source_blocks):
        raise AIReviewError(
            f"review changed block count: {len(source_blocks)} -> {len(reviewed_blocks)}"
        )

    source_timestamps = [block.timestamp for block in source_blocks]
    reviewed_timestamps = [block.timestamp for block in reviewed_blocks]
    if reviewed_timestamps != source_timestamps:
        raise AIReviewError("review changed timestamp values or ordering")

    source_speakers = [block.speaker for block in source_blocks]
    reviewed_speakers = [block.speaker for block in reviewed_blocks]
    if reviewed_speakers != source_speakers:
        raise AIReviewError("review changed speaker labels or speaker ordering")

    for source_block, reviewed_block in zip(source_blocks, reviewed_blocks, strict=True):
        if source_block.text and not reviewed_block.text:
            raise AIReviewError(
                f"review emptied transcript block at {source_block.timestamp}"
            )

    source_chars = sum(len(block.text) for block in source_blocks)
    reviewed_chars = sum(len(block.text) for block in reviewed_blocks)
    if source_chars and not 0.50 <= reviewed_chars / source_chars <= 1.80:
        raise AIReviewError(
            "review length changed beyond conservative safety bounds "
            f"({source_chars} -> {reviewed_chars} characters)"
        )
    return reviewed_blocks


def _group_consecutive_speakers(
    blocks: list[TranscriptBlock],
) -> list[tuple[str, list[str]]]:
    groups: list[tuple[str, list[str]]] = []
    for block in blocks:
        if groups and groups[-1][0] == block.speaker:
            groups[-1][1].append(block.text)
        else:
            groups.append((block.speaker, [block.text]))
    return groups


def render_review_markdown(blocks: list[TranscriptBlock]) -> str:
    parts = ["# media"]
    for speaker, texts in _group_consecutive_speakers(blocks):
        parts.extend([f"**{speaker}**", "\n\n".join(texts)])
    return "\n\n".join(parts).rstrip() + "\n"


def render_review_text(blocks: list[TranscriptBlock]) -> str:
    parts: list[str] = []
    for speaker, texts in _group_consecutive_speakers(blocks):
        parts.extend([f"{speaker}:", "\n\n".join(texts)])
    return "\n\n".join(parts).rstrip() + "\n"


def _atomic_write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{uuid.uuid4().hex}.tmp")
    temporary.write_text(content, encoding="utf-8")
    temporary.replace(path)


def _response_content(payload: dict[str, Any]) -> str:
    try:
        content = payload["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError) as exc:
        raise AIReviewError("review API response did not contain assistant content") from exc
    if not isinstance(content, str) or not content.strip():
        raise AIReviewError("review API returned empty assistant content")
    return _strip_optional_code_fence(content)


def _call_review_api(text: str, config: ReviewAPIConfig) -> str:
    request_body = {
        "model": config.model,
        "messages": [
            {"role": "system", "content": PERSIAN_TRANSCRIPT_REVIEW_PROMPT},
            {"role": "user", "content": text},
        ],
    }
    encoded = json.dumps(request_body, ensure_ascii=False).encode("utf-8")
    retryable_statuses = {408, 409, 425, 429, 500, 502, 503, 504}

    for attempt in range(1, config.max_attempts + 1):
        request = urllib.request.Request(
            config.base_url + "/chat/completions",
            data=encoded,
            headers={
                "Authorization": "Bearer " + config.api_key,
                "Content-Type": "application/json",
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=config.timeout_seconds) as response:
                payload = json.loads(response.read().decode("utf-8"))
            return _response_content(payload)
        except urllib.error.HTTPError as exc:
            if exc.code not in retryable_statuses or attempt == config.max_attempts:
                raise AIReviewError(f"review API HTTP error: {exc.code}") from exc
        except (urllib.error.URLError, TimeoutError, socket.timeout, json.JSONDecodeError) as exc:
            if attempt == config.max_attempts:
                raise AIReviewError("review API request failed after retries") from exc
        time.sleep(min(2 ** (attempt - 1), 20))

    raise AIReviewError("review API request failed")


def review_collection_output(
    collection_root: Path,
    result_number: int,
    *,
    force: bool = False,
    config: ReviewAPIConfig | None = None,
) -> dict[str, Any]:
    if result_number < 1:
        raise AIReviewError("result number must be positive")

    root = collection_root.resolve()
    source = root / "timestamped" / f"{result_number}.md"
    if not source.is_file():
        raise AIReviewError(f"timestamped source does not exist: {source}")

    reviewed_timed = root / "review" / "timestamped" / f"{result_number}.md"
    reviewed_md = root / "review" / "md" / f"{result_number}.md"
    reviewed_txt = root / "review" / "txt" / f"{result_number}.txt"

    review_paths = (reviewed_timed, reviewed_md, reviewed_txt)
    if not force and all(path.is_file() and path.stat().st_size > 0 for path in review_paths):
        return {
            "status": "skipped",
            "reason": "review outputs already complete",
            "result_number": result_number,
            "root": str(root / "review"),
        }

    source_text = source.read_text(encoding="utf-8")
    if reviewed_timed.is_file() and reviewed_timed.stat().st_size > 0 and not force:
        reviewed_text = reviewed_timed.read_text(encoding="utf-8")
        blocks = validate_review(source_text, reviewed_text)
        api_used = False
    else:
        reviewed_text = _call_review_api(source_text, config or ReviewAPIConfig.from_env())
        blocks = validate_review(source_text, reviewed_text)
        _atomic_write(reviewed_timed, reviewed_text.rstrip() + "\n")
        api_used = True

    _atomic_write(reviewed_md, render_review_markdown(blocks))
    _atomic_write(reviewed_txt, render_review_text(blocks))

    return {
        "status": "completed",
        "result_number": result_number,
        "api_used": api_used,
        "timestamped": str(reviewed_timed),
        "markdown": str(reviewed_md),
        "text": str(reviewed_txt),
        "blocks": len(blocks),
    }


def review_collection_output_if_configured(
    collection_root: Path,
    result_number: int,
) -> dict[str, Any]:
    configured = [bool(os.environ.get(name, "").strip()) for name in _REVIEW_ENV]
    if not any(configured):
        return {
            "status": "skipped",
            "reason": "review API is not configured",
            "result_number": result_number,
        }
    if not all(configured):
        raise AIReviewError("review API environment variables are only partially configured")
    return review_collection_output(collection_root, result_number)
