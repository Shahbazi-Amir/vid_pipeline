"""Build a deterministic, API-free handoff package for ChatGPT review."""

from __future__ import annotations

import hashlib
import json
import shutil
import uuid
from pathlib import Path
from typing import Any

from vid_pipeline.state import PipelineState

DEFAULT_CHUNK_CHARS = 24_000

REVIEW_PROMPT = """# دستور بازبینی متن

این بسته خروجی رونویسی ماشینی است و بازبینی باید فقط بر اساس فایل‌های همین بسته انجام شود.

1. غلط‌های واضح ASR، نشانه‌گذاری و فاصله‌گذاری فارسی را اصلاح کن.
2. متن را آزادانه بازنویسی نکن، چیزی حذف نکن و اطلاعات تازه نساز.
3. ترتیب مطالب، زمان‌ها و برچسب گوینده‌ها را حفظ کن.
4. نام اشخاص و اصطلاحات را فقط با شواهد موجود در بسته اصلاح کن.
5. متن را خوانا و پاراگراف‌بندی کن، اما معنای جمله‌ها را تغییر نده.
6. در موارد نامطمئن حدس نزن؛ عبارت را با `[نامطمئن]` مشخص کن.
7. اگر فایل‌های `chunks/` وجود دارند، همه را دقیقاً به ترتیب Manifest بررسی کن و هیچ قطعه‌ای را جا نینداز.
8. خروجی نهایی باید کل متن را پوشش دهد؛ توضیح جانبی را جدا از متن نهایی بنویس.

ابتدا `review-manifest.json` و `source-metadata.json` را بخوان، سپس Transcriptها، گزارش کیفیت و دادهٔ گوینده‌ها را بررسی کن.
"""


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _copy_if_present(source: Path, target: Path) -> bool:
    if not source.is_file():
        return False
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(source, target)
    return True


def _chunk_text(text: str, limit: int) -> list[str]:
    if limit < 1000:
        raise ValueError("chunk_chars must be at least 1000")
    chunks: list[str] = []
    start = 0
    while start < len(text):
        end = min(len(text), start + limit)
        if end < len(text):
            boundary = text.rfind("\n", start + limit // 2, end)
            if boundary > start:
                end = boundary + 1
        chunks.append(text[start:end])
        start = end
    return chunks


def build_chatgpt_handoff(
    job_root: str | Path, *, chunk_chars: int = DEFAULT_CHUNK_CHARS
) -> dict[str, Any]:
    """Materialize a complete review package without invoking an LLM API."""
    root = Path(job_root)
    required = {
        "source-metadata.json": root / "source.json",
        "transcript.raw.json": root / "raw" / "transcript.raw.json",
        "transcript.raw.md": root / "raw" / "transcript.raw.md",
        "transcript.machine.md": root / "machine" / "transcript.machine.md",
        "transcript.machine.txt": root / "machine" / "transcript.machine.txt",
    }
    missing = [str(path) for path in required.values() if not path.is_file()]
    if missing:
        raise ValueError(f"ChatGPT review handoff is missing required files: {missing}")

    review_root = root / "review"
    target = review_root / "chatgpt"
    temporary = review_root / f".chatgpt.{uuid.uuid4().hex}.tmp"
    temporary.mkdir(parents=True, exist_ok=False)
    try:
        for name, source in required.items():
            _copy_if_present(source, temporary / name)
        optional = {
            "audio-quality.json": root / "audio" / "audio-quality.json",
            "diarization.json": root / "diarization" / "diarization.json",
            "accuracy-transcript.json": root / "accuracy" / "transcript.consensus.json",
            "quality-summary.json": root / "review" / "quality-report.json",
        }
        included_optional = [
            name for name, source in optional.items() if _copy_if_present(source, temporary / name)
        ]
        (temporary / "chatgpt-review-prompt.md").write_text(REVIEW_PROMPT, encoding="utf-8")

        machine_text = required["transcript.machine.txt"].read_text(encoding="utf-8")
        chunks = _chunk_text(machine_text, chunk_chars)
        chunk_records: list[dict[str, Any]] = []
        if len(chunks) > 1:
            for index, content in enumerate(chunks, start=1):
                relative = Path("chunks") / f"{index:04d}.txt"
                path = temporary / relative
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(content, encoding="utf-8")
                chunk_records.append(
                    {
                        "index": index,
                        "path": relative.as_posix(),
                        "characters": len(content),
                        "sha256": _sha256(path),
                    }
                )

        files = []
        for path in sorted(item for item in temporary.rglob("*") if item.is_file()):
            relative = path.relative_to(temporary).as_posix()
            if relative == "review-manifest.json":
                continue
            files.append({"path": relative, "size": path.stat().st_size, "sha256": _sha256(path)})
        manifest = {
            "schema_version": 1,
            "review_type": "chatgpt_human_in_the_loop",
            "paid_api_invoked": False,
            "source_transcript": "transcript.machine.txt",
            "source_transcript_sha256": hashlib.sha256(machine_text.encode("utf-8")).hexdigest(),
            "chunk_strategy": {
                "mode": "ordered_lossless_text_slices" if chunk_records else "not_required",
                "chunk_chars": chunk_chars,
                "complete_when_concatenated_in_order": True,
                "chunks": chunk_records,
            },
            "optional_files_included": included_optional,
            "files": files,
        }
        manifest_path = temporary / "review-manifest.json"
        manifest_path.write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
        if target.exists():
            shutil.rmtree(target)
        temporary.replace(target)
    except Exception:
        shutil.rmtree(temporary, ignore_errors=True)
        raise

    outputs = [path for path in target.rglob("*") if path.is_file()]
    details = {
        "status": "completed",
        "package": str(target.resolve()),
        "manifest": str((target / "review-manifest.json").resolve()),
        "chunk_count": len(chunks) if len(chunks) > 1 else 0,
        "paid_api_invoked": False,
    }
    PipelineState(root / "state.json").mark_complete("chatgpt_review", outputs, details)
    result_path = root / "result.json"
    result = json.loads(result_path.read_text(encoding="utf-8")) if result_path.is_file() else {}
    result.update({"chatgpt_review_status": "ready", "chatgpt_review": details})
    result_path.write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    return details
