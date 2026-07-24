"""Auditable review-package orchestration and human verification."""

from __future__ import annotations

import json
import shutil
from dataclasses import asdict
from pathlib import Path
from typing import Any, Iterable

from vid_pipeline.review_analysis import (
    analyze_segments,
    audit_transcript_changes,
    load_glossaries,
)
from vid_pipeline.review_media import extract_clip, retranscribe_items
from vid_pipeline.review_render import assistant_chunks, review_html, review_markdown
from vid_pipeline.review_types import (
    TERMINAL_PUNCTUATION,
    ReviewConfig,
    ReviewError,
    load_json,
    normalize_text,
    sha256_file,
    utc_now,
)


def _write_state(root: Path, outputs: list[Path], details: dict[str, Any]) -> None:
    path = root / "state.json"
    if not path.exists():
        return
    state = load_json(path)
    state.setdefault("stages", {})["review"] = {
        "status": "completed",
        "updated_at": utc_now(),
        "output_paths": [str(item.resolve()) for item in outputs],
        "details": details,
        "error": "",
    }
    state["updated_at"] = utc_now()
    path.write_text(json.dumps(state, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _mark_review_required(root: Path, manifest: Path) -> None:
    path = root / "result.json"
    if not path.exists():
        return
    result = load_json(path)
    result["pre_human_review_status"] = result.get("review_status")
    result.update(
        {
            "status": "human_review_required",
            "review_status": "human_review_required",
            "review_package": str(manifest),
            "human_audio_verification": False,
        }
    )
    path.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def build_review_package(
    job_root: str | Path,
    *,
    config: ReviewConfig | None = None,
    glossary_paths: Iterable[str | Path] = (),
) -> dict[str, Any]:
    config = config or ReviewConfig()
    root = Path(job_root)
    raw_path = root / "raw" / "transcript.raw.json"
    machine_path = root / "machine" / "transcript.machine.txt"
    final_path = root / "final" / "transcript.final.txt"
    audio_path = root / "audio" / "audio-16k-mono.wav"
    for path in (raw_path, machine_path, final_path):
        if not path.exists():
            raise ReviewError(f"Required review input does not exist: {path}")
    review_dir = root / "review"
    review_dir.mkdir(parents=True, exist_ok=True)
    raw = load_json(raw_path)
    aliases = load_glossaries(glossary_paths)
    items = analyze_segments(raw, config=config, glossary_aliases=aliases)
    warnings: list[str] = []
    if config.extract_clips:
        if not audio_path.exists():
            warnings.append("audio_missing_clips_not_created")
        else:
            for item in items:
                relative = f"clips/{item['id']}.wav"
                start = max(0.0, float(item["start"]) - config.clip_context_seconds)
                end = float(item["end"]) + config.clip_context_seconds
                error = extract_clip(audio_path, review_dir / relative, start, end)
                if error:
                    warnings.append(f"clip_{item['id']}: {error}")
                else:
                    item["clip"] = relative
    warnings += retranscribe_items(items, review_dir=review_dir, config=config, glossary_aliases=aliases)
    audit = audit_transcript_changes(
        machine_path.read_text(encoding="utf-8"), final_path.read_text(encoding="utf-8")
    )
    audit_path = review_dir / "editorial-audit.json"
    audit_path.write_text(json.dumps(audit, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    uncertain_path = review_dir / "uncertain-spans.json"
    uncertain_path.write_text(
        json.dumps({"schema_version": 1, "generated_at": utc_now(), "config": asdict(config), "items": items}, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    assistant_path = review_dir / "assistant-review-package.json"
    assistant_path.write_text(
        json.dumps({"schema_version": 1, "source": "audio_and_whisper_only", "external_reference_used": False, "chunks": assistant_chunks(list(raw.get("segments") or []), items)}, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    manifest_path = review_dir / "manifest.json"
    manifest = {
        "schema_version": 1,
        "status": "human_review_required" if items else "human_review_optional",
        "generated_at": utc_now(),
        "job_root": str(root),
        "segment_count": len(raw.get("segments") or []),
        "review_item_count": len(items),
        "required_item_count": len(items),
        "external_reference_used": False,
        "source_files": {"raw_json": str(raw_path), "machine_text": str(machine_path), "final_text": str(final_path), "audio": str(audio_path) if audio_path.exists() else ""},
        "source_sha256": {"raw_json": sha256_file(raw_path), "machine_text": sha256_file(machine_path), "final_text": sha256_file(final_path)},
        "files": {"manifest": str(manifest_path), "uncertain_spans": str(uncertain_path), "editorial_audit": str(audit_path), "assistant_package": str(assistant_path), "review_markdown": str(review_dir / "review.md"), "review_html": str(review_dir / "review.html"), "corrections_template": str(review_dir / "corrections.template.json")},
        "warnings": warnings,
    }
    (review_dir / "review.md").write_text(review_markdown(manifest, items), encoding="utf-8")
    (review_dir / "review.html").write_text(review_html(manifest, items), encoding="utf-8")
    (review_dir / "corrections.template.json").write_text(
        json.dumps({"schema_version": 1, "reviewer": "", "reviewed_at": "", "items": [{"id": item["id"], "segment_id": item["segment_id"], "decision": "pending", "replacement": item["proposed_text"]} for item in items]}, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    outputs = [manifest_path, uncertain_path, audit_path, assistant_path, review_dir / "review.md", review_dir / "review.html", review_dir / "corrections.template.json"]
    _write_state(root, outputs, {"status": manifest["status"], "review_item_count": len(items), "warnings": warnings})
    _mark_review_required(root, manifest_path)
    return manifest


def _paragraphs(texts: Iterable[str], max_words: int) -> list[str]:
    output: list[str] = []
    current: list[str] = []
    count = 0
    for value in texts:
        text = normalize_text(value) or "[نامفهوم]"
        words = text.split()
        if current and count + len(words) > max_words:
            output.append(normalize_text(" ".join(current)))
            current, count = [], 0
        current.append(text)
        count += len(words)
        if text.endswith(TERMINAL_PUNCTUATION) and count >= max_words // 2:
            output.append(normalize_text(" ".join(current)))
            current, count = [], 0
    if current:
        output.append(normalize_text(" ".join(current)))
    return output


def apply_human_review(
    job_root: str | Path,
    corrections_path: str | Path,
    *,
    reviewer: str = "",
    promote: bool = False,
    paragraph_words: int = 90,
) -> dict[str, Any]:
    root = Path(job_root)
    raw_path = root / "raw" / "transcript.raw.json"
    uncertain_path = root / "review" / "uncertain-spans.json"
    if not raw_path.exists() or not uncertain_path.exists():
        raise ReviewError("Build the review package before applying human corrections.")
    raw = load_json(raw_path)
    uncertain = load_json(uncertain_path)
    corrections = load_json(corrections_path)
    reviewer_name = normalize_text(reviewer or str(corrections.get("reviewer") or ""))
    if not reviewer_name:
        raise ReviewError("A non-empty reviewer name is required for human verification.")
    correction_map = {int(item["segment_id"]): item for item in corrections.get("items") or [] if isinstance(item, dict) and item.get("segment_id") is not None}
    review_map = {int(item["segment_id"]): item for item in uncertain.get("items") or []}
    unresolved: list[str] = []
    for item in uncertain.get("items") or []:
        correction = correction_map.get(int(item["segment_id"]))
        decision = str((correction or {}).get("decision") or "pending")
        if decision not in {"accept_original", "accept_suggestion", "edit"}:
            unresolved.append(str(item["id"]))
        elif decision == "edit" and not normalize_text(str(correction.get("replacement") or "")):
            unresolved.append(str(item["id"]))
    if unresolved:
        raise ReviewError("Human review is incomplete; unresolved required items: " + ", ".join(unresolved))
    reviewed: list[dict[str, Any]] = []
    for index, segment in enumerate(raw.get("segments") or []):
        segment_id = int(segment.get("id", index))
        source = normalize_text(str(segment.get("text") or "")) or "[نامفهوم]"
        correction = correction_map.get(segment_id)
        decision = str((correction or {}).get("decision") or "accept_original")
        if decision == "accept_suggestion" and segment_id in review_map:
            text = normalize_text(str(review_map[segment_id].get("proposed_text") or source))
        elif decision == "edit":
            text = normalize_text(str((correction or {}).get("replacement") or ""))
        else:
            text = source
        if not text:
            raise ReviewError(f"Human correction made segment {segment_id} empty.")
        reviewed.append({"segment_id": segment_id, "start": float(segment.get("start", 0.0) or 0.0), "end": float(segment.get("end", 0.0) or 0.0), "source_text": source, "reviewed_text": text, "decision": decision})
    paragraphs = _paragraphs((item["reviewed_text"] for item in reviewed), paragraph_words)
    human_dir = root / "human"
    human_dir.mkdir(parents=True, exist_ok=True)
    text_path = human_dir / "transcript.human.txt"
    markdown_path = human_dir / "transcript.human.md"
    verification_path = human_dir / "verification.json"
    text_path.write_text("\n\n".join(paragraphs).rstrip() + "\n", encoding="utf-8")
    markdown_path.write_text(f"# متن بازبینی‌شده انسانی\n\n> بازبین: {reviewer_name}  \n> تاریخ بازبینی: {utc_now()}  \n> تمام segmentهای علامت‌خورده با صوت تعیین تکلیف شده‌اند.\n\n" + "\n\n".join(paragraphs).rstrip() + "\n", encoding="utf-8")
    verification = {"schema_version": 1, "status": "human_verified", "review_status": "human_verified", "reviewer": reviewer_name, "verified_at": utc_now(), "segment_count": len(reviewed), "required_items_resolved": len(review_map), "unresolved_items": [], "source_raw_sha256": sha256_file(raw_path), "corrections_sha256": sha256_file(corrections_path), "human_text_sha256": sha256_file(text_path), "human_markdown_sha256": sha256_file(markdown_path), "promoted_to_final": bool(promote), "segments": reviewed}
    verification_path.write_text(json.dumps(verification, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    if promote:
        final_dir = root / "final"
        final_dir.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(text_path, final_dir / "transcript.final.txt")
        shutil.copyfile(markdown_path, final_dir / "transcript.final.md")
        result_path = root / "result.json"
        result = load_json(result_path) if result_path.exists() else {"schema_version": 4}
        result.update({"status": "completed", "review_status": "human_verified", "human_audio_verification": True, "human_reviewer": reviewer_name, "human_verification_report": str(verification_path), "final_text": str(final_dir / "transcript.final.txt"), "final_markdown": str(final_dir / "transcript.final.md")})
        result_path.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return verification


__all__ = ["ReviewConfig", "ReviewError", "analyze_segments", "apply_human_review", "audit_transcript_changes", "build_review_package", "load_glossaries"]
