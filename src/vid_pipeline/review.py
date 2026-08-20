"""Auditable review-package orchestration with evidence-backed verification."""

from __future__ import annotations

import json
import shutil
import zipfile
from collections.abc import Iterable
from dataclasses import asdict
from pathlib import Path
from typing import Any

from vid_pipeline.review_analysis import (
    analyze_segments,
    audit_transcript_changes,
    load_glossaries,
)
from vid_pipeline.review_media import extract_clip, retranscribe_items
from vid_pipeline.review_quality import build_quality_report
from vid_pipeline.review_render import assistant_chunks, review_html, review_markdown
from vid_pipeline.review_subtitles import render_srt, render_vtt
from vid_pipeline.review_types import (
    TERMINAL_PUNCTUATION,
    ReviewConfig,
    ReviewError,
    load_json,
    normalize_text,
    sha256_file,
    utc_now,
)

AI_REVIEWER_MARKERS = (
    "chatgpt",
    "openai",
    "gpt",
    "llm",
    "claude",
    "gemini",
    "copilot",
    "artificial intelligence",
)
VALID_DECISIONS = {"accept_original", "accept_suggestion", "edit", "unclear"}


def _looks_like_ai_reviewer(name: str) -> bool:
    folded = normalize_text(name).casefold()
    return any(marker in folded for marker in AI_REVIEWER_MARKERS)


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


def _mark_review_required(root: Path, manifest: Path, review_status: str) -> None:
    path = root / "result.json"
    if not path.exists():
        return
    result = load_json(path)
    result["pre_human_review_status"] = result.get("review_status")
    result["review_status"] = review_status
    if review_status == "human_review_required":
        result["status"] = "human_review_required"
    result.update(
        {
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
    for path in (raw_path, machine_path):
        if not path.exists():
            raise ReviewError(f"Required review input does not exist: {path}")
    # A quality-gated job may intentionally have no final transcript yet.
    # In that case the machine text is the comparison baseline, not a fake final.
    comparison_path = final_path if final_path.exists() else machine_path
    review_dir = root / "review"
    review_dir.mkdir(parents=True, exist_ok=True)
    raw = load_json(raw_path)
    consensus_path = root / "accuracy" / "transcript.consensus.json"
    quality_input = load_json(consensus_path) if consensus_path.exists() else raw
    aliases = load_glossaries(glossary_paths)
    items = analyze_segments(quality_input, config=config, glossary_aliases=aliases)
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
    warnings += retranscribe_items(
        items,
        review_dir=review_dir,
        config=config,
        glossary_aliases=aliases,
    )
    audit = audit_transcript_changes(
        machine_path.read_text(encoding="utf-8"),
        comparison_path.read_text(encoding="utf-8"),
    )
    audit_path = review_dir / "editorial-audit.json"
    audit_path.write_text(
        json.dumps(audit, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    uncertain_path = review_dir / "uncertain-spans.json"
    uncertain_path.write_text(
        json.dumps(
            {
                "schema_version": 2,
                "generated_at": utc_now(),
                "config": asdict(config),
                "items": items,
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    assistant_path = review_dir / "assistant-review-package.json"
    assistant_path.write_text(
        json.dumps(
            {
                "schema_version": 2,
                "source": "audio_and_asr_only",
                "external_reference_used": False,
                "verification_class": "ai_assistance_not_human_verification",
                "chunks": assistant_chunks(list(quality_input.get("segments") or []), items),
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    quality_path = review_dir / "quality-report.json"
    quality_path.write_text(
        json.dumps(build_quality_report(quality_input), ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    review_srt = review_dir / "transcript.review.srt"
    review_vtt = review_dir / "transcript.review.vtt"
    review_srt.write_text(render_srt(quality_input.get("segments") or []), encoding="utf-8")
    review_vtt.write_text(render_vtt(quality_input.get("segments") or []), encoding="utf-8")
    manifest_path = review_dir / "manifest.json"
    manifest = {
        "schema_version": 2,
        "status": "human_review_required" if items else "human_review_optional",
        "generated_at": utc_now(),
        "job_root": str(root),
        "segment_count": len(raw.get("segments") or []),
        "review_item_count": len(items),
        "required_item_count": len(items),
        "external_reference_used": False,
        "quality_source": str(consensus_path if consensus_path.exists() else raw_path),
        "verification_policy": {
            "ai_review_can_human_verify": False,
            "human_audio_confirmation_required": True,
            "per_item_audio_evidence_required": bool(items),
        },
        "source_files": {
            "raw_json": str(raw_path),
            "machine_text": str(machine_path),
            "comparison_text": str(comparison_path),
            "audio": str(audio_path) if audio_path.exists() else "",
        },
        "source_sha256": {
            "raw_json": sha256_file(raw_path),
            "machine_text": sha256_file(machine_path),
            "comparison_text": sha256_file(comparison_path),
        },
        "files": {
            "manifest": str(manifest_path),
            "uncertain_spans": str(uncertain_path),
            "editorial_audit": str(audit_path),
            "assistant_package": str(assistant_path),
            "quality_report": str(quality_path),
            "review_srt": str(review_srt),
            "review_vtt": str(review_vtt),
            "review_markdown": str(review_dir / "review.md"),
            "review_html": str(review_dir / "review.html"),
            "corrections_template": str(review_dir / "corrections.template.json"),
        },
        "warnings": warnings,
    }
    (review_dir / "review.md").write_text(review_markdown(manifest, items), encoding="utf-8")
    (review_dir / "review.html").write_text(review_html(manifest, items), encoding="utf-8")
    (review_dir / "corrections.template.json").write_text(
        json.dumps(
            {
                "schema_version": 2,
                "reviewer": "",
                "reviewed_at": "",
                "review_type": "human_audio",
                "verification": {
                    "method": "human_audio",
                    "audio_review_confirmed": False,
                },
                "items": [
                    {
                        "id": item["id"],
                        "segment_id": item["segment_id"],
                        "decision": "pending",
                        "replacement": item["proposed_text"],
                        "audio_reviewed": False,
                        "notes": "",
                    }
                    for item in items
                ],
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    archive_path = root / "final" / "review-package.zip"
    manifest["files"]["review_archive"] = str(archive_path)
    manifest_path.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    archive_path.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(archive_path, "w", zipfile.ZIP_DEFLATED) as archive:
        for file_path in sorted(review_dir.rglob("*")):
            if file_path.is_file():
                archive.write(file_path, arcname=file_path.relative_to(review_dir))
    outputs = [
        manifest_path,
        uncertain_path,
        audit_path,
        assistant_path,
        quality_path,
        review_srt,
        review_vtt,
        review_dir / "review.md",
        review_dir / "review.html",
        review_dir / "corrections.template.json",
        archive_path,
    ]
    _write_state(
        root,
        outputs,
        {"status": manifest["status"], "review_item_count": len(items), "warnings": warnings},
    )
    _mark_review_required(root, manifest_path, manifest["status"])
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


def _review_maps(
    uncertain: dict[str, Any], corrections: dict[str, Any]
) -> tuple[dict[int, dict[str, Any]], dict[int, dict[str, Any]]]:
    correction_map = {
        int(item["segment_id"]): item
        for item in corrections.get("items") or []
        if isinstance(item, dict) and item.get("segment_id") is not None
    }
    review_map = {
        int(item["segment_id"]): item for item in uncertain.get("items") or []
    }
    return correction_map, review_map


def _validate_decisions(
    uncertain: dict[str, Any],
    correction_map: dict[int, dict[str, Any]],
    *,
    require_audio_evidence: bool,
) -> None:
    unresolved: list[str] = []
    for item in uncertain.get("items") or []:
        correction = correction_map.get(int(item["segment_id"]))
        decision = str((correction or {}).get("decision") or "pending")
        valid = decision in VALID_DECISIONS
        if decision == "edit" and not normalize_text(str((correction or {}).get("replacement") or "")):
            valid = False
        if require_audio_evidence and (correction or {}).get("audio_reviewed") is not True:
            valid = False
        if not valid:
            unresolved.append(str(item["id"]))
    if unresolved:
        evidence = " with per-item audio evidence" if require_audio_evidence else ""
        raise ReviewError(
            f"Review is incomplete{evidence}; unresolved required items: " + ", ".join(unresolved)
        )


def _build_reviewed_segments(
    raw: dict[str, Any],
    correction_map: dict[int, dict[str, Any]],
    review_map: dict[int, dict[str, Any]],
) -> list[dict[str, Any]]:
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
        elif decision == "unclear":
            text = "[نامفهوم]"
        else:
            text = source
        if not text:
            raise ReviewError(f"Review correction made segment {segment_id} empty.")
        reviewed.append(
            {
                "segment_id": segment_id,
                "start": float(segment.get("start", 0.0) or 0.0),
                "end": float(segment.get("end", 0.0) or 0.0),
                "source_text": source,
                "reviewed_text": text,
                "decision": decision,
                "audio_reviewed": bool((correction or {}).get("audio_reviewed")),
            }
        )
    return reviewed


def _write_reviewed_files(
    directory: Path,
    prefix: str,
    reviewed: list[dict[str, Any]],
    reviewer_name: str,
    paragraph_words: int,
    *,
    human_audio_verified: bool,
) -> tuple[Path, Path, Path, Path]:
    directory.mkdir(parents=True, exist_ok=True)
    paragraphs = _paragraphs((item["reviewed_text"] for item in reviewed), paragraph_words)
    text_path = directory / f"transcript.{prefix}.txt"
    markdown_path = directory / f"transcript.{prefix}.md"
    srt_path = directory / f"transcript.{prefix}.srt"
    vtt_path = directory / f"transcript.{prefix}.vtt"
    text_path.write_text("\n\n".join(paragraphs).rstrip() + "\n", encoding="utf-8")
    label = "بازبینی انسانی مبتنی بر صوت" if human_audio_verified else "بازبینی کمکی هوش مصنوعی"
    markdown_path.write_text(
        f"# {label}\n\n> بازبین: {reviewer_name}  \n> تاریخ: {utc_now()}  \n"
        + (
            "> شواهد شنیدن صوت برای تمام موارد اجباری ثبت شده است.\n\n"
            if human_audio_verified
            else "> این خروجی human/audio verified نیست و برای نهایی‌سازی انسانی معتبر نیست.\n\n"
        )
        + "\n\n".join(paragraphs).rstrip()
        + "\n",
        encoding="utf-8",
    )
    srt_path.write_text(render_srt(reviewed, text_key="reviewed_text"), encoding="utf-8")
    vtt_path.write_text(render_vtt(reviewed, text_key="reviewed_text"), encoding="utf-8")
    return text_path, markdown_path, srt_path, vtt_path


def apply_ai_review(
    job_root: str | Path,
    corrections_path: str | Path,
    *,
    reviewer: str = "AI",
    paragraph_words: int = 90,
) -> dict[str, Any]:
    """Apply AI-assisted corrections without claiming human/audio verification."""
    root = Path(job_root)
    raw_path = root / "raw" / "transcript.raw.json"
    uncertain_path = root / "review" / "uncertain-spans.json"
    if not raw_path.exists() or not uncertain_path.exists():
        raise ReviewError("Build the review package before applying AI review.")
    raw = load_json(raw_path)
    uncertain = load_json(uncertain_path)
    corrections = load_json(corrections_path)
    reviewer_name = normalize_text(reviewer or str(corrections.get("reviewer") or "AI")) or "AI"
    correction_map, review_map = _review_maps(uncertain, corrections)
    _validate_decisions(uncertain, correction_map, require_audio_evidence=False)
    reviewed = _build_reviewed_segments(raw, correction_map, review_map)
    ai_dir = root / "ai"
    text_path, markdown_path, srt_path, vtt_path = _write_reviewed_files(
        ai_dir, "ai", reviewed, reviewer_name, paragraph_words, human_audio_verified=False
    )
    report = {
        "schema_version": 2,
        "status": "ai_reviewed",
        "review_status": "ai_reviewed",
        "reviewer": reviewer_name,
        "reviewed_at": utc_now(),
        "human_audio_verification": False,
        "eligible_for_human_verified": False,
        "promoted_to_final": False,
        "segment_count": len(reviewed),
        "source_raw_sha256": sha256_file(raw_path),
        "corrections_sha256": sha256_file(corrections_path),
        "ai_text_sha256": sha256_file(text_path),
        "segments": reviewed,
    }
    report_path = ai_dir / "review.json"
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    result_path = root / "result.json"
    if result_path.exists():
        result = load_json(result_path)
        result.update(
            {
                "review_status": "ai_reviewed",
                "human_audio_verification": False,
                "ai_review_report": str(report_path),
            }
        )
        result_path.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return report


def apply_human_review(
    job_root: str | Path,
    corrections_path: str | Path,
    *,
    reviewer: str = "",
    promote: bool = False,
    paragraph_words: int = 90,
) -> dict[str, Any]:
    """Apply evidence-backed human audio review.

    A reviewer name and decisions alone are not verification.  Human verified
    status requires the source audio, a top-level human-audio confirmation and
    ``audio_reviewed=true`` on every required review item.
    """
    root = Path(job_root)
    raw_path = root / "raw" / "transcript.raw.json"
    uncertain_path = root / "review" / "uncertain-spans.json"
    audio_path = root / "audio" / "audio-16k-mono.wav"
    if not raw_path.exists() or not uncertain_path.exists():
        raise ReviewError("Build the review package before applying human corrections.")
    if not audio_path.is_file():
        raise ReviewError("Human audio verification requires the source review audio.")
    raw = load_json(raw_path)
    uncertain = load_json(uncertain_path)
    corrections = load_json(corrections_path)
    reviewer_name = normalize_text(reviewer or str(corrections.get("reviewer") or ""))
    if not reviewer_name:
        raise ReviewError("A non-empty human reviewer name is required.")
    if _looks_like_ai_reviewer(reviewer_name):
        raise ReviewError(
            "AI/LLM reviewers cannot produce human_verified status; use apply_ai_review instead."
        )
    verification_meta = corrections.get("verification") or {}
    if (
        str(corrections.get("review_type") or "") != "human_audio"
        or verification_meta.get("method") != "human_audio"
        or verification_meta.get("audio_review_confirmed") is not True
    ):
        raise ReviewError(
            "Human verification requires explicit review_type=human_audio and audio_review_confirmed=true."
        )
    correction_map, review_map = _review_maps(uncertain, corrections)
    _validate_decisions(uncertain, correction_map, require_audio_evidence=True)
    reviewed = _build_reviewed_segments(raw, correction_map, review_map)
    human_dir = root / "human"
    text_path, markdown_path, srt_path, vtt_path = _write_reviewed_files(
        human_dir, "human", reviewed, reviewer_name, paragraph_words, human_audio_verified=True
    )
    verification_path = human_dir / "verification.json"
    verification = {
        "schema_version": 2,
        "status": "human_verified",
        "review_status": "human_verified",
        "verification_method": "human_audio",
        "human_audio_verification": True,
        "reviewer": reviewer_name,
        "verified_at": utc_now(),
        "segment_count": len(reviewed),
        "required_items_resolved": len(review_map),
        "audio_evidence_items": len(review_map),
        "unresolved_items": [],
        "source_raw_sha256": sha256_file(raw_path),
        "source_audio_sha256": sha256_file(audio_path),
        "corrections_sha256": sha256_file(corrections_path),
        "human_text_sha256": sha256_file(text_path),
        "human_markdown_sha256": sha256_file(markdown_path),
        "human_srt_sha256": sha256_file(srt_path),
        "human_vtt_sha256": sha256_file(vtt_path),
        "promoted_to_final": bool(promote),
        "segments": reviewed,
    }
    verification_path.write_text(
        json.dumps(verification, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    if promote:
        from vid_pipeline.final_export import export_final_outputs

        final_dir = root / "final"
        final_dir.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(text_path, final_dir / "transcript.final.txt")
        shutil.copyfile(markdown_path, final_dir / "transcript.final.md")
        shutil.copyfile(srt_path, final_dir / "transcript.final.srt")
        shutil.copyfile(vtt_path, final_dir / "transcript.final.vtt")
        shutil.copyfile(verification_path, final_dir / "human-verification.json")
        result_path = root / "result.json"
        result = load_json(result_path) if result_path.exists() else {"schema_version": 4}
        result.update(
            {
                "status": "completed",
                "review_status": "human_verified",
                "human_audio_verification": True,
                "human_reviewer": reviewer_name,
                "human_verification_report": str(verification_path),
                "final_text": str(final_dir / "transcript.final.txt"),
                "final_markdown": str(final_dir / "transcript.final.md"),
                "final_srt": str(final_dir / "transcript.final.srt"),
                "final_vtt": str(final_dir / "transcript.final.vtt"),
            }
        )
        result_path.write_text(
            json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
        export_final_outputs(root)
    return verification


__all__ = [
    "ReviewConfig",
    "ReviewError",
    "analyze_segments",
    "apply_ai_review",
    "apply_human_review",
    "audit_transcript_changes",
    "build_review_package",
    "load_glossaries",
]
