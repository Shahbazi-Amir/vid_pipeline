"""Create review packages and record genuine human review."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from vid_pipeline.errors import ReviewRequiredError
from vid_pipeline.models import EpisodeSpec
from vid_pipeline.state import sha256_file
from vid_pipeline.transcribe import format_timestamp


def create_review_package(
    spec: EpisodeSpec,
    raw_json: str | Path,
    destination: str | Path,
) -> Path:
    data = json.loads(Path(raw_json).read_text(encoding="utf-8"))
    lines = [
        f"# {spec.title or spec.program}",
        "",
        f"{spec.program} — {spec.season}، قسمت {spec.season_episode}",
        "",
        f"**قسمت کل مجموعه:** {spec.overall_episode}",
        f"**گویندگان:** {', '.join(spec.speakers)}",
        f"**منبع رسمی:** {spec.source_url or '[ثبت نشده]'}",
        f"**ویدئو:** {spec.video_url or '[ثبت نشده]'}",
        "",
        "> این فایل برای بازبینی انسانی ساخته شده است. متن را با صوت تطبیق دهید؛ محتوای جدید اضافه نکنید و بخش واقعاً غیرقابل‌تشخیص را با `[نامفهوم]` مشخص کنید.",
        "",
        "## متن زمان‌دار برای بازبینی",
        "",
    ]
    for segment in data.get("segments", []):
        flags = segment.get("review_flags") or []
        warning = f" — نیازمند توجه: {', '.join(flags)}" if flags else ""
        lines.append(
            f"### {format_timestamp(float(segment['start']))} تا {format_timestamp(float(segment['end']))}{warning}"
        )
        lines.append("")
        lines.append(str(segment.get("text", "")).strip() or "[نامفهوم]")
        lines.append("")
    path = Path(destination)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")
    return path


def mark_reviewed(
    audio_path: str | Path,
    final_transcript: str | Path,
    receipt_path: str | Path,
    reviewer: str,
    confirmed_audio_review: bool,
) -> Path:
    if not confirmed_audio_review:
        raise ReviewRequiredError("Audio review must be explicitly confirmed.")
    audio = Path(audio_path)
    transcript = Path(final_transcript)
    if not audio.exists() or not transcript.exists():
        raise ReviewRequiredError("Audio and final transcript must both exist.")
    content = transcript.read_text(encoding="utf-8").strip()
    if len(content) < 100:
        raise ReviewRequiredError("Final transcript is unexpectedly short.")
    receipt = {
        "schema_version": 1,
        "review_status": "reviewed",
        "reviewer": reviewer.strip() or "human-reviewer",
        "reviewed_at": datetime.now(timezone.utc).isoformat(),
        "audio_sha256": sha256_file(audio),
        "transcript_sha256": sha256_file(transcript),
        "audio_review_confirmed": True,
    }
    destination = Path(receipt_path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(
        json.dumps(receipt, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    return destination


def verify_review(final_transcript: str | Path, receipt_path: str | Path) -> dict[str, object]:
    transcript = Path(final_transcript)
    receipt = Path(receipt_path)
    if not transcript.exists() or not receipt.exists():
        raise ReviewRequiredError("Reviewed transcript or review receipt is missing.")
    data = json.loads(receipt.read_text(encoding="utf-8"))
    if data.get("review_status") != "reviewed" or not data.get("audio_review_confirmed"):
        raise ReviewRequiredError("Review receipt is not valid.")
    if data.get("transcript_sha256") != sha256_file(transcript):
        raise ReviewRequiredError("Transcript changed after review; review it again.")
    return data
