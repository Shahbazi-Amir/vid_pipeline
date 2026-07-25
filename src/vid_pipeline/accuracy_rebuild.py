"""Rebuild machine/editorial outputs from the multi-pass consensus transcript."""
from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import Any

from vid_pipeline.clean import clean_transcript
from vid_pipeline.editorial import (
    EditorialConfig,
    EditorialMetadata,
    assess_transcript_preservation,
    edit_transcript,
    raw_transcript_text,
)


def rebuild_from_accuracy(
    job_root: str | Path,
    consensus_json: str | Path,
    *,
    title: str = "",
    source_url: str = "",
    max_words: int = 90,
    editorial_config: EditorialConfig | None = None,
    editorial_metadata: EditorialMetadata | None = None,
) -> dict[str, Any]:
    root = Path(job_root)
    source = Path(consensus_json)
    if not source.exists():
        raise FileNotFoundError(source)
    machine_dir = root / "machine"
    final_dir = root / "final"
    machine_dir.mkdir(parents=True, exist_ok=True)
    final_dir.mkdir(parents=True, exist_ok=True)
    machine_markdown = machine_dir / "transcript.machine.md"
    machine_text = machine_dir / "transcript.machine.txt"
    final_markdown = final_dir / "transcript.final.md"
    final_text = final_dir / "transcript.final.txt"
    editorial_report = final_dir / "editorial-report.json"
    clean_details = clean_transcript(
        source,
        machine_markdown,
        machine_text,
        title=title,
        source_url=source_url,
        max_words=max_words,
    )
    fallback_used = False
    if editorial_config is None:
        shutil.copyfile(machine_markdown, final_markdown)
        shutil.copyfile(machine_text, final_text)
        editorial_details: dict[str, Any] = {
            "status": "accuracy_consensus_machine_only",
            "fallback_used": False,
            "provider": "deterministic",
        }
    else:
        try:
            editorial_details = edit_transcript(
                source,
                final_markdown,
                final_text,
                metadata=editorial_metadata
                or EditorialMetadata(title=title, source_url=source_url),
                config=editorial_config,
            )
        except Exception as exc:
            shutil.copyfile(machine_markdown, final_markdown)
            shutil.copyfile(machine_text, final_text)
            fallback_used = True
            editorial_details = {
                "status": "machine_fallback",
                "fallback_used": True,
                "fallback_reason": f"accuracy_editorial_error: {type(exc).__name__}: {exc}",
            }
    validation = dict(editorial_details.get("final_validation") or {})
    if not validation:
        validation = assess_transcript_preservation(
            raw_transcript_text(source),
            final_text.read_text(encoding="utf-8"),
        )
    if not validation["accepted"]:
        shutil.copyfile(machine_markdown, final_markdown)
        shutil.copyfile(machine_text, final_text)
        fallback_used = True
        editorial_details = {
            "status": "machine_fallback",
            "fallback_used": True,
            "fallback_reason": "accuracy_editorial_failed_preservation",
        }
        validation = assess_transcript_preservation(
            raw_transcript_text(source),
            final_text.read_text(encoding="utf-8"),
        )
    if not validation["accepted"]:
        raise RuntimeError("Accuracy rebuild failed content-preservation validation")
    editorial_details["final_validation"] = validation
    editorial_report.write_text(
        json.dumps(editorial_details, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    result_path = root / "result.json"
    result = (
        json.loads(result_path.read_text(encoding="utf-8"))
        if result_path.exists()
        else {"schema_version": 5}
    )
    result.update(
        {
            "schema_version": max(5, int(result.get("schema_version", 0) or 0)),
            "status": "completed_with_fallback" if fallback_used else "completed",
            "review_status": "accuracy_consensus_with_fallback"
            if fallback_used
            else "accuracy_consensus_completed",
            "accuracy_consensus_json": str(source),
            "machine_markdown": str(machine_markdown),
            "machine_text": str(machine_text),
            "final_markdown": str(final_markdown),
            "final_text": str(final_text),
            "editorial_report": str(editorial_report),
            "content_preservation": validation,
            "human_audio_verification": False,
        }
    )
    result_path.write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return {
        "status": result["review_status"],
        "clean": clean_details,
        "editorial": editorial_details,
        "content_preservation": validation,
        "files": {
            "machine_markdown": str(machine_markdown),
            "machine_text": str(machine_text),
            "final_markdown": str(final_markdown),
            "final_text": str(final_text),
            "editorial_report": str(editorial_report),
        },
    }


__all__ = ["rebuild_from_accuracy"]
