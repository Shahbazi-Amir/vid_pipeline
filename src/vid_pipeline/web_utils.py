"""Pure helpers for the local Streamlit operations console."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import Any

ACTIVE_JOB_STATUSES = {"queued", "preparing", "processing", "quality_check", "rendering"}
RETRYABLE_JOB_STATUSES = {"failed", "review_required", "cancelled"}
STAGE_ORDER = (
    "queued",
    "materializing_source",
    "normalize_audio",
    "transcribe_primary",
    "targeted_retry",
    "clean_transcript",
    "quality_scoring",
    "quality_check",
    "rendering",
    "completed",
)
STAGE_LABELS = {
    "queued": "در صف",
    "materializing_source": "دریافت و آماده‌سازی ورودی",
    "canonical_core": "هسته پردازش",
    "normalize_audio": "استخراج و نرمال‌سازی صدا",
    "transcribe_primary": "رونویسی اصلی",
    "targeted_retry": "بازآزمایی بخش‌های مشکوک",
    "clean_transcript": "پاک‌سازی محافظه‌کارانه متن",
    "quality_scoring": "امتیازدهی کیفیت",
    "quality_check": "دروازه کیفیت",
    "rendering": "ساخت خروجی‌ها",
    "completed": "تکمیل‌شده",
    "review_required": "نیازمند بازبینی",
    "failed": "ناموفق",
    "cancelled": "لغوشده",
}


def parse_timestamp(value: Any) -> datetime | None:
    text = str(value or "").strip()
    if not text:
        return None
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


def job_timing(job: dict[str, Any], *, now: datetime | None = None) -> dict[str, float | None]:
    current = now or datetime.now(UTC)
    if current.tzinfo is None:
        current = current.replace(tzinfo=UTC)
    created = parse_timestamp(job.get("created_at"))
    started = parse_timestamp(job.get("started_at"))
    completed = parse_timestamp(job.get("completed_at"))
    queue_wait = (started - created).total_seconds() if created and started else None
    execution = (
        (completed - started).total_seconds()
        if started and completed
        else (current - started).total_seconds() if started else None
    )
    total = (
        (completed - created).total_seconds()
        if created and completed
        else (current - created).total_seconds() if created else None
    )
    return {
        "queue_wait_seconds": max(0.0, queue_wait) if queue_wait is not None else None,
        "execution_seconds": max(0.0, execution) if execution is not None else None,
        "total_seconds": max(0.0, total) if total is not None else None,
    }


def format_duration(seconds: Any) -> str:
    if seconds is None or seconds == "":
        return "—"
    try:
        total = max(0, int(round(float(seconds))))
    except (TypeError, ValueError):
        return "—"
    hours, remainder = divmod(total, 3600)
    minutes, secs = divmod(remainder, 60)
    if hours:
        return f"{hours:d}:{minutes:02d}:{secs:02d}"
    return f"{minutes:02d}:{secs:02d}"


def source_label(job: dict[str, Any]) -> str:
    source = job.get("source") or {}
    source_type = str(source.get("type") or "upload")
    if source_type == "url":
        return str(source.get("url") or "URL")
    if source_type == "github_release":
        return f"{source.get('repository', '')}@{source.get('tag', '')} / {source.get('asset', '')}".strip()
    return str(job.get("file_name") or source.get("file_name") or job.get("upload_id") or "Upload")


def parse_url_lines(value: str) -> list[str]:
    return [line.strip() for line in value.splitlines() if line.strip()]


def parse_release_lines(value: str) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for line_number, raw in enumerate(value.splitlines(), 1):
        line = raw.strip()
        if not line:
            continue
        parts = [part.strip() for part in line.split("|")]
        if len(parts) != 3 or not all(parts):
            raise ValueError(
                f"خط {line_number}: فرمت باید owner/repo | tag | asset باشد."
            )
        repository, tag, asset = parts
        if repository.count("/") != 1:
            raise ValueError(f"خط {line_number}: repository باید owner/repo باشد.")
        if Path(asset).name != asset:
            raise ValueError(f"خط {line_number}: asset فقط باید نام فایل باشد.")
        rows.append({"repository": repository, "tag": tag, "asset": asset})
    return rows


def preferred_text_artifact(artifact_names: list[str], status: str) -> str | None:
    names = set(artifact_names)
    candidates = (
        ["delivery/transcript.txt", "delivery/transcript.md"]
        if status == "completed"
        else ["machine/transcript.machine.txt", "raw/transcript.raw.md"]
    )
    for candidate in candidates:
        if candidate in names:
            return candidate
    for name in artifact_names:
        if name.endswith(".txt") or name.endswith(".md"):
            return name
    return None


def downloadable_artifacts(artifact_names: list[str]) -> list[str]:
    preferred_suffixes = (".txt", ".md", ".srt", ".vtt", ".json")
    return [name for name in artifact_names if name.endswith(preferred_suffixes)]


def stage_rows(job: dict[str, Any]) -> list[dict[str, Any]]:
    history = [item for item in (job.get("stage_history") or []) if isinstance(item, dict)]
    events = {str(item.get("stage")): item for item in history if item.get("stage")}
    current = str(job.get("current_stage") or job.get("status") or "queued")
    status = str(job.get("status") or "queued")
    rows: list[dict[str, Any]] = []
    reached_current = False
    for stage in STAGE_ORDER:
        event = events.get(stage)
        if stage == current:
            state = "active" if status in ACTIVE_JOB_STATUSES else "done"
            reached_current = True
        elif event:
            state = "done"
        elif not reached_current and current in STAGE_ORDER and STAGE_ORDER.index(stage) < STAGE_ORDER.index(current):
            state = "done"
        else:
            state = "pending"
        rows.append(
            {
                "stage": stage,
                "label": STAGE_LABELS.get(stage, stage),
                "state": state,
                "at": (event or {}).get("at"),
                "progress_percent": (event or {}).get("progress_percent"),
            }
        )
    if status in {"review_required", "failed", "cancelled"}:
        rows.append(
            {
                "stage": status,
                "label": STAGE_LABELS.get(status, status),
                "state": "done",
                "at": job.get("completed_at"),
                "progress_percent": job.get("progress_percent"),
            }
        )
    return rows
