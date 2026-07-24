"""Local, open-source editorial reconstruction for noisy Persian ASR output."""

from __future__ import annotations

import json
import re
import time
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Protocol

from vid_pipeline.errors import PipelineError

_FENCE_RE = re.compile(r"^```(?:markdown|md|text)?\s*|\s*```$", re.IGNORECASE)
_SPACE_RE = re.compile(r"[ \t]+")
_MARKDOWN_PREFIX_RE = re.compile(r"^(#{1,6}\s+|>\s*|[-*+]\s+)")
_SENTENCE_BOUNDARY_RE = re.compile(r"(?<=[.!؟!?])\s+")


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


def build_editorial_chunks(segments: list[dict[str, Any]], max_chars: int = 6500) -> list[str]:
    """Build ordered, timecoded chunks without splitting Whisper segments."""
    if max_chars < 2000:
        raise ValueError("chunk_chars must be at least 2000")
    chunks: list[str] = []
    current: list[str] = []
    size = 0
    for index, segment in enumerate(segments):
        text = _SPACE_RE.sub(" ", str(segment.get("text") or "")).strip() or "[نامفهوم]"
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
    return """شما ویراستار ارشد رونویسی فارسی هستید. ورودی، خروجی پرخطای تشخیص گفتار است.
متن را با حفظ کامل معنا و ترتیب گفتار بازسازی کن.
قواعد قطعی:
1) هیچ واقعیت، نام، عدد، نقل‌قول، آیه یا ادعای تازه‌ای اضافه نکن.
2) «واژه‌نامه و دستور تکمیلی» فقط برای املای صحیح نام‌ها، مکان‌ها و تشخیص گوینده معتبر است؛ آن را به‌عنوان محتوای تازه وارد متن نکن.
3) خطاهای آوایی و دستوری را فقط وقتی از بافت قابل بازیابی‌اند اصلاح کن؛ در غیر این صورت [نامفهوم] بنویس.
4) تکرار ماشینی، مکث و کلمات پرکننده را حذف کن، اما هیچ استدلال یا جملۀ معناداری را خلاصه یا حذف نکن.
5) اگر مشخصات می‌گوید فقط یک گوینده وجود دارد، همان نام را یک‌بار در آغاز متن بنویس و هرگز «مجری» یا گویندۀ دیگری اختراع نکن.
6) در گفت‌وگو، گویندگان را با برچسب بولد جدا کن. اگر هویت روشن نیست، **گوینده:** بنویس.
7) برای متن بلند از تیترهای سطح دوم (##) استفاده کن؛ برای کلیپ کوتاه یک تیتر کافی است.
8) هر پاراگراف حداکثر دو جمله داشته باشد و بین پاراگراف‌ها حتماً یک خط خالی بگذار.
9) فهرست بلند نام‌ها، مکان‌ها یا نمونه‌ها را در چند پاراگراف کوتاه و خوانا تقسیم کن.
10) نثر را فارسی معیار، روان، دقیق و وفادار نگه دار؛ بازنویسی ادبی یا خلاصه‌سازی نکن.
11) شناسه‌ها و زمان‌نماهای S0001 را در خروجی نیاور.
12) فقط بدنۀ Markdown را برگردان و هیچ توضیحی دربارۀ فرایند ننویس.
"""


def _quality_instructions() -> str:
    return """شما کنترل‌گر نهایی کیفیت رونویسی فارسی هستید.
نسخۀ پیشنهادی را با متن خام و واژه‌نامۀ داده‌شده تطبیق بده و فقط خطاها را اصلاح کن.
- نام‌ها و مکان‌ها را دقیقاً با املای واژه‌نامه بنویس، اما نام کامل را فقط وقتی جایگزین کن که همان شخص در صوت ذکر شده باشد.
- اعداد، سن‌ها و عبارت‌های پایانی را حذف نکن.
- گویندۀ تازه، جمله، ادعا یا تفسیر تازه نساز.
- اگر فقط یک گوینده معرفی شده، برچسب او را یک‌بار در ابتدای متن نگه دار.
- هر پاراگراف حداکثر دو جمله داشته باشد و بین پاراگراف‌ها یک خط خالی باشد.
- فهرست‌های طولانی را به چند پاراگراف کوتاه تقسیم کن.
- فارسی معیار، نیم‌فاصله و نشانه‌گذاری را اصلاح کن.
- فقط بدنۀ Markdown نهایی را برگردان.
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
            "> این متن فقط از روی صوت ویدئو استخراج و سپس با یک مدل متن‌باز محلی بازسازی شده است. عبارت‌های غیرقابل‌بازیابی با `[نامفهوم]` مشخص می‌شوند؛ برای استناد کلمه‌به‌کلمه، تطبیق نهایی با صوت لازم است.",
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
    """Reconstruct a readable transcript from ordered Whisper segments."""
    metadata = metadata or EditorialMetadata()
    config = config or EditorialConfig()
    data = json.loads(Path(raw_json).read_text(encoding="utf-8"))
    segments = list(data.get("segments") or [])
    if not segments:
        raise PipelineError("Raw transcript has no segments to edit.")

    chunks = build_editorial_chunks(segments, config.chunk_chars)
    active_client = client or OllamaChatClient(config)
    outputs: list[str] = []
    previous = ""
    metadata_text = _metadata_text(metadata) or "- اطلاعات تکمیلی موجود نیست"

    for index, chunk in enumerate(chunks, start=1):
        prompt = f"مشخصات محتوا:\n{metadata_text}\n\nاین بخش {index} از {len(chunks)} است.\n"
        if previous:
            prompt += (
                "انتهای بخش قبلی فقط برای پیوستگی؛ آن را تکرار نکن:\n"
                f"{previous[-config.previous_context_chars:]}\n\n"
            )
        prompt += f"متن خام:\n{chunk}"
        edited = _clean_model_markdown(
            active_client.edit(instructions=_instructions(), input_text=prompt)
        )
        if not edited:
            raise PipelineError(f"Editorial chunk {index} was empty.")

        if client is None and config.second_pass:
            review_prompt = (
                f"مشخصات و واژه‌نامه:\n{metadata_text}\n\n"
                f"متن خام همین بخش:\n{chunk}\n\n"
                f"نسخۀ پیشنهادی:\n{edited}"
            )
            reviewed_chunk = _clean_model_markdown(
                active_client.edit(
                    instructions=_quality_instructions(),
                    input_text=review_prompt,
                )
            )
            if reviewed_chunk:
                edited = reviewed_chunk

        outputs.append(edited)
        previous = edited

    body = "\n\n".join(_deduplicate_boundaries(outputs)).strip()
    body = enforce_readable_paragraphs(body)
    reviewed = render_reviewed_markdown(metadata, body)
    md_path = Path(output_markdown)
    txt_path = Path(output_text)
    md_path.parent.mkdir(parents=True, exist_ok=True)
    txt_path.parent.mkdir(parents=True, exist_ok=True)
    md_path.write_text(reviewed, encoding="utf-8")
    txt_path.write_text(markdown_to_text(reviewed), encoding="utf-8")
    return {
        "status": "local_editorial_completed",
        "model": config.model,
        "provider": "ollama",
        "segments": len(segments),
        "chunks": len(chunks),
        "quality_passes": 2 if client is None and config.second_pass else 1,
        "markdown": str(md_path),
        "text": str(txt_path),
        "human_audio_verification": False,
    }
