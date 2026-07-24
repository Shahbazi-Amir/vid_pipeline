"""Local, open-source editorial reconstruction for noisy Persian ASR output."""

from __future__ import annotations

import json
import re
import time
import urllib.error
import urllib.request
from collections import Counter
from dataclasses import dataclass, field
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any, Protocol

from vid_pipeline.errors import PipelineError

_FENCE_RE = re.compile(r"^```(?:markdown|md|text)?\s*|\s*```$", re.IGNORECASE)
_SPACE_RE = re.compile(r"[ \t]+")
_MARKDOWN_PREFIX_RE = re.compile(r"^(#{1,6}\s+|>\s*|[-*+]\s+)")
_SENTENCE_BOUNDARY_RE = re.compile(r"(?<=[.!؟!?])\s+")
_TIMECODE_RE = re.compile(r"^\[S\d+\s+\d{2}:\d{2}:\d{2}-\d{2}:\d{2}:\d{2}\]\s*")
_DIACRITICS_RE = re.compile(r"[\u0610-\u061A\u064B-\u065F\u0670\u06D6-\u06ED]")
_TOKEN_RE = re.compile(r"[\w\u0600-\u06FF]+", re.UNICODE)
_ARABIC_TO_PERSIAN = str.maketrans(
    {
        "ي": "ی",
        "ى": "ی",
        "ك": "ک",
        "ۀ": "ه",
        "ة": "ه",
        "ؤ": "و",
        "إ": "ا",
        "أ": "ا",
        "ٱ": "ا",
        "‌": " ",
        "۰": "0",
        "۱": "1",
        "۲": "2",
        "۳": "3",
        "۴": "4",
        "۵": "5",
        "۶": "6",
        "۷": "7",
        "۸": "8",
        "۹": "9",
        "٠": "0",
        "١": "1",
        "٢": "2",
        "٣": "3",
        "٤": "4",
        "٥": "5",
        "٦": "6",
        "٧": "7",
        "٨": "8",
        "٩": "9",
    }
)


@dataclass(slots=True)
class EditorialMetadata:
    title: str = ""
    source_url: str = ""
    program: str = ""
    network: str = ""
    date: str = ""
    guest: str = ""
    duration: str = ""
    speakers: list[str] = field(default_factory=list)
    context: str = ""


@dataclass(slots=True)
class EditorialConfig:
    """Configuration for the local Ollama editorial model."""

    model: str = "qwen3:8b"
    base_url: str = "http://127.0.0.1:11434"
    chunk_chars: int = 6500
    previous_context_chars: int = 1200
    max_output_tokens: int = 9000
    context_window: int = 16384
    temperature: float = 0.05
    timeout_seconds: int = 600
    retries: int = 3
    second_pass: bool = True
    min_output_ratio: float = 0.65
    max_output_ratio: float = 1.55
    min_token_recall: float = 0.28
    min_sequence_similarity: float = 0.18
    fallback_on_invalid: bool = True


class EditorialClient(Protocol):
    def edit(self, *, instructions: str, input_text: str) -> str: ...


class OllamaChatClient:
    """Dependency-free client for a local Ollama server."""

    def __init__(self, config: EditorialConfig) -> None:
        self.config = config

    def edit(self, *, instructions: str, input_text: str) -> str:
        payload = {
            "model": self.config.model,
            "stream": False,
            "think": False,
            "messages": [
                {"role": "system", "content": instructions},
                {"role": "user", "content": input_text},
            ],
            "options": {
                "temperature": self.config.temperature,
                "num_ctx": self.config.context_window,
                "num_predict": self.config.max_output_tokens,
                "repeat_penalty": 1.08,
            },
        }
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        url = self.config.base_url.rstrip("/") + "/api/chat"
        last_error: Exception | None = None
        for attempt in range(self.config.retries):
            request = urllib.request.Request(
                url,
                data=body,
                method="POST",
                headers={"Content-Type": "application/json"},
            )
            try:
                with urllib.request.urlopen(request, timeout=self.config.timeout_seconds) as response:
                    data = json.loads(response.read().decode("utf-8"))
                text = _ollama_output_text(data)
                if not text:
                    raise PipelineError("Local editorial model returned an empty response.")
                return text
            except urllib.error.HTTPError as exc:
                message = exc.read().decode("utf-8", errors="replace")
                last_error = PipelineError(
                    f"Local editorial server failed ({exc.code}): {message[:1000]}"
                )
                if exc.code not in {408, 409, 429, 500, 502, 503, 504}:
                    break
            except (OSError, ValueError) as exc:
                last_error = exc
            if attempt + 1 < self.config.retries:
                time.sleep(2**attempt)
        raise PipelineError(
            "Local editorial stage failed. Make sure Ollama is running and the model is "
            f"installed ({self.config.model}): {last_error}"
        )


def _ollama_output_text(data: dict[str, Any]) -> str:
    message = data.get("message") or {}
    content = message.get("content")
    if isinstance(content, str):
        return content.strip()
    response = data.get("response")
    return response.strip() if isinstance(response, str) else ""


def _timestamp(seconds: float) -> str:
    total = max(0, int(seconds))
    hours, remainder = divmod(total, 3600)
    minutes, secs = divmod(remainder, 60)
    return f"{hours:02d}:{minutes:02d}:{secs:02d}"


def _segment_text(segment: dict[str, Any]) -> str:
    return _SPACE_RE.sub(" ", str(segment.get("text") or "")).strip() or "[نامفهوم]"


def raw_transcript_text(raw_json: str | Path) -> str:
    """Return every non-empty Whisper segment in its original order."""

    data = json.loads(Path(raw_json).read_text(encoding="utf-8"))
    segments = list(data.get("segments") or [])
    if not segments:
        raise PipelineError("Raw transcript has no segments.")
    return " ".join(_segment_text(segment) for segment in segments).strip()


def build_editorial_chunks(segments: list[dict[str, Any]], max_chars: int = 6500) -> list[str]:
    """Build ordered, timecoded chunks without splitting Whisper segments."""

    if max_chars < 2000:
        raise ValueError("chunk_chars must be at least 2000")
    chunks: list[str] = []
    current: list[str] = []
    size = 0
    for index, segment in enumerate(segments):
        text = _segment_text(segment)
        segment_id = segment.get("id", index)
        line = (
            f"[S{int(segment_id):04d} {_timestamp(float(segment.get('start') or 0))}"
            f"-{_timestamp(float(segment.get('end') or 0))}] {text}"
        )
        if current and size + len(line) + 1 > max_chars:
            chunks.append("\n".join(current))
            current = []
            size = 0
        current.append(line)
        size += len(line) + 1
    if current:
        chunks.append("\n".join(current))
    return chunks


def _chunk_plain_text(chunk: str) -> str:
    parts: list[str] = []
    for line in chunk.splitlines():
        value = _TIMECODE_RE.sub("", line).strip()
        if value:
            parts.append(value)
    return " ".join(parts).strip()


def _metadata_text(metadata: EditorialMetadata) -> str:
    values = [
        ("عنوان", metadata.title),
        ("برنامه", metadata.program),
        ("شبکه/ناشر", metadata.network),
        ("تاریخ", metadata.date),
        ("گوینده/مهمان", metadata.guest),
        ("مدت", metadata.duration),
        ("منبع", metadata.source_url),
        ("گویندگان قطعی", "، ".join(metadata.speakers)),
        ("واژه‌نامه و دستور تکمیلی", metadata.context),
    ]
    return "\n".join(f"- {key}: {value}" for key, value in values if value)


def _instructions() -> str:
    return """شما ویراستار رونویسی فارسی هستید. ورودی، خروجی پرخطای تشخیص گفتار است.
متن را بدون خلاصه‌سازی و با حفظ کامل ترتیب و تمام اطلاعات بازسازی کن.
قواعد قطعی:
1) هیچ واقعیت، نام، عدد، نقل‌قول، آیه یا ادعای تازه‌ای اضافه نکن.
2) هیچ جمله، مثال، نام، عدد، عبارت پایانی یا بخش معناداری را حذف نکن.
3) طول خروجی باید نزدیک به طول متن خام باشد؛ کوتاه‌سازی و خلاصه‌سازی ممنوع است.
4) «واژه‌نامه و دستور تکمیلی» فقط برای املای نام‌ها و مکان‌ها معتبر است.
5) خطاهای آوایی را فقط وقتی از بافت قابل بازیابی‌اند اصلاح کن؛ وگرنه [نامفهوم] بنویس.
6) تکرار ماشینی و کلمات پرکننده را می‌توان حذف کرد، اما استدلال یا محتوای گفتار را نه.
7) شناسه‌ها و زمان‌نماهای S0001 را در خروجی نیاور.
8) فقط بدنۀ Markdown را برگردان و درباره فرایند توضیح نده.
"""


def _quality_instructions() -> str:
    return """نسخۀ پیشنهادی را با متن خام تطبیق بده و فقط خطاهای روشن را اصلاح کن.
- هیچ جمله، نام، عدد، مثال، آیه یا عبارت پایانی را حذف نکن.
- متن را خلاصه نکن و طول آن را به‌طور معنادار کاهش نده.
- گویندۀ تازه، جمله، ادعا یا تفسیر تازه نساز.
- فقط بدنۀ Markdown کامل را برگردان.
"""


def _clean_model_markdown(text: str) -> str:
    value = _FENCE_RE.sub("", text.strip()).strip()
    lines = [line.rstrip() for line in value.splitlines()]
    compact: list[str] = []
    blank = False
    for line in lines:
        if not line.strip():
            if compact and not blank:
                compact.append("")
            blank = True
            continue
        compact.append(line)
        blank = False
    return "\n".join(compact).strip()


def _split_sentences(paragraph: str) -> list[str]:
    normalized = _SPACE_RE.sub(" ", paragraph.replace("\n", " ")).strip()
    return [item.strip() for item in _SENTENCE_BOUNDARY_RE.split(normalized) if item.strip()]


def enforce_readable_paragraphs(
    body: str,
    *,
    max_sentences: int = 2,
    max_chars: int = 360,
) -> str:
    """Force readable blank-line-separated paragraphs after model generation."""

    if max_sentences < 1:
        raise ValueError("max_sentences must be at least 1")
    if max_chars < 120:
        raise ValueError("max_chars must be at least 120")

    output: list[str] = []
    blocks = [item.strip() for item in re.split(r"\n{2,}", body) if item.strip()]
    for block in blocks:
        if block.startswith(("#", ">", "- ", "* ", "+ ", "```")):
            output.append(block)
            continue

        sentences = _split_sentences(block)
        if len(sentences) <= 1 and len(block) <= max_chars:
            output.append(block)
            continue

        current: list[str] = []
        current_size = 0
        for sentence in sentences or [block]:
            projected = current_size + len(sentence) + (1 if current else 0)
            if current and (len(current) >= max_sentences or projected > max_chars):
                output.append(" ".join(current))
                current = []
                current_size = 0
            current.append(sentence)
            current_size += len(sentence) + (1 if current_size else 0)
        if current:
            output.append(" ".join(current))

    return "\n\n".join(output).strip()


def _deduplicate_boundaries(parts: list[str]) -> list[str]:
    output: list[str] = []
    seen_tail = ""
    for part in parts:
        paragraphs = [item.strip() for item in re.split(r"\n{2,}", part) if item.strip()]
        kept: list[str] = []
        for paragraph in paragraphs:
            key = re.sub(r"\W+", " ", paragraph, flags=re.UNICODE).strip().casefold()
            if key and key == seen_tail:
                continue
            kept.append(paragraph)
            seen_tail = key
        if kept:
            output.append("\n\n".join(kept))
    return output


def _tokens(text: str) -> list[str]:
    value = _DIACRITICS_RE.sub("", str(text or "").translate(_ARABIC_TO_PERSIAN))
    value = value.replace("\u200f", " ").replace("\u200e", " ")
    value = re.sub(r"[#>*_`~\[\](){}|]+", " ", value)
    return [token.casefold() for token in _TOKEN_RE.findall(value)]


def assess_transcript_preservation(
    source: str,
    candidate: str,
    *,
    min_output_ratio: float = 0.65,
    max_output_ratio: float = 1.55,
    min_token_recall: float = 0.28,
    min_sequence_similarity: float = 0.18,
) -> dict[str, Any]:
    """Measure whether an edited candidate still contains the source transcript."""

    source_tokens = _tokens(source)
    candidate_tokens = _tokens(candidate)
    source_count = len(source_tokens)
    candidate_count = len(candidate_tokens)
    if source_count == 0:
        raise ValueError("source transcript has no tokens")

    length_ratio = candidate_count / source_count
    source_counter = Counter(source_tokens)
    candidate_counter = Counter(candidate_tokens)
    overlap = sum((source_counter & candidate_counter).values())
    token_recall = overlap / source_count
    sequence_similarity = SequenceMatcher(
        None,
        source_tokens,
        candidate_tokens,
        autojunk=False,
    ).ratio()
    accepted = (
        min_output_ratio <= length_ratio <= max_output_ratio
        and (
            token_recall >= min_token_recall
            or sequence_similarity >= min_sequence_similarity
        )
    )
    reasons: list[str] = []
    if length_ratio < min_output_ratio:
        reasons.append("candidate_too_short")
    if length_ratio > max_output_ratio:
        reasons.append("candidate_too_long")
    if token_recall < min_token_recall and sequence_similarity < min_sequence_similarity:
        reasons.append("insufficient_source_overlap")

    return {
        "accepted": accepted,
        "source_tokens": source_count,
        "candidate_tokens": candidate_count,
        "length_ratio": round(length_ratio, 4),
        "token_recall": round(token_recall, 4),
        "sequence_similarity": round(sequence_similarity, 4),
        "reasons": reasons,
    }


def _validation(source: str, candidate: str, config: EditorialConfig) -> dict[str, Any]:
    return assess_transcript_preservation(
        source,
        candidate,
        min_output_ratio=config.min_output_ratio,
        max_output_ratio=config.max_output_ratio,
        min_token_recall=config.min_token_recall,
        min_sequence_similarity=config.min_sequence_similarity,
    )


def render_reviewed_markdown(metadata: EditorialMetadata, body: str) -> str:
    title = metadata.title.strip() or "متن ویدئو"
    lines = [f"# {title}", ""]
    summary: list[str] = []
    if metadata.program:
        program = f"برنامۀ «{metadata.program}»"
        if metadata.network:
            program += f" — {metadata.network}"
        summary.append(program)
    elif metadata.network:
        summary.append(metadata.network)
    if metadata.date:
        summary.append(f"تاریخ: {metadata.date}")
    if metadata.guest:
        summary.append(f"گوینده: {metadata.guest}")
    if metadata.duration:
        summary.append(f"مدت: {metadata.duration}")
    if metadata.source_url:
        summary.append(f"منبع: {metadata.source_url}")
    for item in summary:
        lines.append(item + "  ")
    if summary:
        lines.append("")
    lines.extend(
        [
            "> این متن فقط از روی صوت استخراج شده است. ویرایش محلی فقط وقتی پذیرفته می‌شود که پوشش کامل متن خام حفظ شود؛ در غیر این صورت همان بخش از خروجی ماشینی استفاده می‌شود.",
            "",
            body.strip(),
            "",
        ]
    )
    return "\n".join(lines).rstrip() + "\n"


def markdown_to_text(markdown: str) -> str:
    lines: list[str] = []
    for raw_line in markdown.splitlines():
        line = _MARKDOWN_PREFIX_RE.sub("", raw_line).replace("**", "").replace("`", "")
        lines.append(line.rstrip())
    return "\n".join(lines).strip() + "\n"


def edit_transcript(
    raw_json: str | Path,
    output_markdown: str | Path,
    output_text: str | Path,
    *,
    metadata: EditorialMetadata | None = None,
    config: EditorialConfig | None = None,
    client: EditorialClient | None = None,
) -> dict[str, Any]:
    """Edit Whisper segments while deterministically preventing content loss."""

    metadata = metadata or EditorialMetadata()
    config = config or EditorialConfig()
    data = json.loads(Path(raw_json).read_text(encoding="utf-8"))
    segments = list(data.get("segments") or [])
    if not segments:
        raise PipelineError("Raw transcript has no segments to edit.")

    chunks = build_editorial_chunks(segments, config.chunk_chars)
    active_client = client or OllamaChatClient(config)
    outputs: list[str] = []
    fallback_chunks: list[int] = []
    rejected_passes: list[dict[str, Any]] = []
    chunk_metrics: list[dict[str, Any]] = []
    previous = ""
    metadata_text = _metadata_text(metadata) or "- اطلاعات تکمیلی موجود نیست"

    for index, chunk in enumerate(chunks, start=1):
        source_chunk = _chunk_plain_text(chunk)
        prompt = f"مشخصات محتوا:\n{metadata_text}\n\nاین بخش {index} از {len(chunks)} است.\n"
        if previous:
            prompt += (
                "انتهای بخش قبلی فقط برای پیوستگی؛ آن را تکرار نکن:\n"
                f"{previous[-config.previous_context_chars:]}\n\n"
            )
        prompt += f"متن خام:\n{chunk}"

        edited = ""
        try:
            edited = _clean_model_markdown(
                active_client.edit(instructions=_instructions(), input_text=prompt)
            )
        except Exception as exc:
            rejected_passes.append(
                {"chunk": index, "pass": 1, "reason": "editorial_error", "error": str(exc)}
            )

        first_metrics = _validation(source_chunk, edited, config) if edited else {
            "accepted": False,
            "source_tokens": len(_tokens(source_chunk)),
            "candidate_tokens": 0,
            "length_ratio": 0.0,
            "token_recall": 0.0,
            "sequence_similarity": 0.0,
            "reasons": ["empty_or_failed_response"],
        }

        if not first_metrics["accepted"]:
            rejected_passes.append(
                {"chunk": index, "pass": 1, "reason": "preservation_failed", **first_metrics}
            )
            if not config.fallback_on_invalid:
                raise PipelineError(
                    f"Editorial chunk {index} failed content-preservation validation: "
                    f"{first_metrics['reasons']}"
                )
            edited = source_chunk
            fallback_chunks.append(index)
            accepted_metrics = _validation(source_chunk, edited, config)
        else:
            accepted_metrics = first_metrics

        if client is None and config.second_pass and index not in fallback_chunks:
            review_prompt = (
                f"مشخصات و واژه‌نامه:\n{metadata_text}\n\n"
                f"متن خام همین بخش:\n{chunk}\n\n"
                f"نسخۀ پیشنهادی:\n{edited}"
            )
            reviewed_chunk = ""
            try:
                reviewed_chunk = _clean_model_markdown(
                    active_client.edit(
                        instructions=_quality_instructions(),
                        input_text=review_prompt,
                    )
                )
            except Exception as exc:
                rejected_passes.append(
                    {"chunk": index, "pass": 2, "reason": "review_error", "error": str(exc)}
                )
            if reviewed_chunk:
                reviewed_metrics = _validation(source_chunk, reviewed_chunk, config)
                if reviewed_metrics["accepted"]:
                    edited = reviewed_chunk
                    accepted_metrics = reviewed_metrics
                else:
                    rejected_passes.append(
                        {
                            "chunk": index,
                            "pass": 2,
                            "reason": "preservation_failed",
                            **reviewed_metrics,
                        }
                    )

        outputs.append(edited)
        previous = edited
        chunk_metrics.append({"chunk": index, **accepted_metrics})

    body = "\n\n".join(_deduplicate_boundaries(outputs)).strip()
    body = enforce_readable_paragraphs(body)
    full_source = " ".join(_segment_text(segment) for segment in segments).strip()
    final_metrics = _validation(full_source, body, config)
    whole_document_fallback = False
    if not final_metrics["accepted"]:
        if not config.fallback_on_invalid:
            raise PipelineError(
                "Editorial output failed full-transcript preservation validation: "
                f"{final_metrics['reasons']}"
            )
        body = enforce_readable_paragraphs(full_source)
        final_metrics = _validation(full_source, body, config)
        whole_document_fallback = True
        fallback_chunks = list(range(1, len(chunks) + 1))

    reviewed = render_reviewed_markdown(metadata, body)
    md_path = Path(output_markdown)
    txt_path = Path(output_text)
    md_path.parent.mkdir(parents=True, exist_ok=True)
    txt_path.parent.mkdir(parents=True, exist_ok=True)
    md_path.write_text(reviewed, encoding="utf-8")
    txt_path.write_text(markdown_to_text(reviewed), encoding="utf-8")

    fallback_used = bool(fallback_chunks or whole_document_fallback)
    return {
        "status": (
            "local_editorial_completed_with_fallback"
            if fallback_used
            else "local_editorial_completed"
        ),
        "model": config.model,
        "provider": "ollama",
        "segments": len(segments),
        "chunks": len(chunks),
        "quality_passes": 2 if client is None and config.second_pass else 1,
        "accepted_chunks": len(chunks) - len(set(fallback_chunks)),
        "fallback_chunks": sorted(set(fallback_chunks)),
        "fallback_used": fallback_used,
        "whole_document_fallback": whole_document_fallback,
        "chunk_validation": chunk_metrics,
        "rejected_passes": rejected_passes,
        "final_validation": final_metrics,
        "markdown": str(md_path),
        "text": str(txt_path),
        "human_audio_verification": False,
    }
