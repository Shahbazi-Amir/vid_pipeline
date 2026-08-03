"""Build the small, user-facing transcript delivery package."""

from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import Any

from vid_pipeline.state import PipelineState

OUTPUT_NAMES = ("transcript.md", "transcript.txt", "transcript.timestamped.md")


def _load(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _stamp(value: Any) -> str:
    if isinstance(value, bool):
        raise ValueError("boolean timestamp is invalid")
    seconds = int(float(value))
    if seconds < 0:
        raise ValueError("negative timestamp is invalid")
    hours, remainder = divmod(seconds, 3600)
    minutes, seconds = divmod(remainder, 60)
    return f"{hours:02d}:{minutes:02d}:{seconds:02d}"


def _valid_segments(payload: dict[str, Any]) -> list[dict[str, Any]]:
    valid: list[dict[str, Any]] = []
    for segment in payload.get("segments") or []:
        text = str(segment.get("reviewed_text") or segment.get("text") or "").strip()
        try:
            start = float(segment["start"])
            end = float(segment["end"])
        except (KeyError, TypeError, ValueError):
            continue
        if not text or start < 0 or end < start:
            continue
        valid.append({
            "start": start, "end": end, "text": text,
            **({"speaker": segment["speaker"]} if segment.get("speaker") else {}),
            **({"speaker_role": segment["speaker_role"]} if segment.get("speaker_role") else {}),
            **({"speaker_role_confidence": segment["speaker_role_confidence"]} if segment.get("speaker_role_confidence") is not None else {}),
        })
    return valid


def select_timestamp_source(job_root: str | Path) -> tuple[Path, list[dict[str, Any]]]:
    """Select best text unless it would destroy a finer speaker timeline."""

    root = Path(job_root)
    candidates = (
        root / "human" / "verification.json",
        root / "accuracy" / "transcript.consensus.json",
        root / "machine" / "transcript.machine.json",
        root / "raw" / "transcript.raw.json",
    )
    available: list[tuple[Path, list[dict[str, Any]]]] = []
    for path in candidates:
        if path.is_file():
            segments = _valid_segments(_load(path))
            if segments:
                available.append((path, segments))
    if available:
        text_path, text_segments = available[0]

        def resolution(item: tuple[Path, list[dict[str, Any]]]) -> tuple[int, int]:
            speaker_rows = [row for row in item[1] if row.get("speaker")]
            return len({str(row["speaker"]) for row in speaker_rows}), len(speaker_rows)

        timeline_path, timeline_segments = max(available, key=resolution)
        if resolution((text_path, text_segments)) >= resolution((timeline_path, timeline_segments)):
            return text_path, text_segments
        # Without word timings, splitting a reviewed coarse segment across a
        # finer speaker timeline would duplicate or invent text. Preserve the
        # already aligned timeline and its text rather than collapsing speakers.
        return timeline_path, timeline_segments
    raise ValueError("No transcript source contains valid, real segment timestamps.")


def render_timestamped(segments: list[dict[str, Any]], *, title: str = "") -> str:
    heading = f"# {title.strip()}" if title.strip() else "# متن زمان‌بندی‌شده"
    lines = [heading, ""]
    for segment in segments:
        label = _speaker_label(segment)
        header = f"[{_stamp(segment['start'])} → {_stamp(segment['end'])}]"
        lines.extend([f"{header} **{label}**" if label else header, "", segment["text"], ""])
    return "\n".join(lines).rstrip() + "\n"


def _speaker_label(segment: dict[str, Any]) -> str:
    if segment.get("speaker_role"):
        return str(segment["speaker_role"])
    speaker = str(segment.get("speaker") or "")
    if speaker.startswith("SPEAKER_") and speaker[8:].isdigit():
        number = str(int(speaker[8:]) + 1).translate(str.maketrans("0123456789", "۰۱۲۳۴۵۶۷۸۹"))
        return f"گوینده {number}"
    return speaker


def _render_speaker_markdown(segments: list[dict[str, Any]], title: str) -> str:
    lines = [f"# {title.strip()}" if title.strip() else "# Transcript", ""]
    for segment in segments:
        label = _speaker_label(segment)
        if label:
            lines.extend([f"**{label}**", ""])
        lines.extend([segment["text"], ""])
    return "\n".join(lines).rstrip() + "\n"


def _render_speaker_text(segments: list[dict[str, Any]]) -> str:
    lines = []
    for segment in segments:
        label = _speaker_label(segment)
        if label:
            lines.append(f"{label}:")
        lines.extend([segment["text"], ""])
    return "\n".join(lines).rstrip() + "\n"


def export_final_outputs(job_root: str | Path) -> dict[str, Any]:
    """Regenerate exactly three deliverables without deleting internal state."""

    root = Path(job_root)
    final_dir = root / "final"
    delivery = root / "delivery"
    markdown_source = final_dir / "transcript.final.md"
    text_source = final_dir / "transcript.final.txt"
    if not markdown_source.is_file() or not text_source.is_file():
        raise ValueError("Final Markdown and text transcripts are required for export.")
    source, segments = select_timestamp_source(root)
    metadata_path = root / "source.json"
    metadata = _load(metadata_path) if metadata_path.is_file() else {}

    temporary = root / ".delivery.tmp"
    if temporary.exists():
        shutil.rmtree(temporary)
    temporary.mkdir(parents=True)
    if any(segment.get("speaker") for segment in segments):
        (temporary / OUTPUT_NAMES[0]).write_text(
            _render_speaker_markdown(segments, str(metadata.get("title") or "")), encoding="utf-8"
        )
        (temporary / OUTPUT_NAMES[1]).write_text(_render_speaker_text(segments), encoding="utf-8")
    else:
        shutil.copyfile(markdown_source, temporary / OUTPUT_NAMES[0])
        shutil.copyfile(text_source, temporary / OUTPUT_NAMES[1])
    (temporary / OUTPUT_NAMES[2]).write_text(
        render_timestamped(segments, title=str(metadata.get("title") or "")), encoding="utf-8"
    )
    if delivery.exists():
        shutil.rmtree(delivery)
    temporary.replace(delivery)

    outputs = {name: str((delivery / filename).resolve()) for name, filename in zip(
        ("markdown", "text", "timestamped_markdown"), OUTPUT_NAMES, strict=True
    )}
    details = {"status": "completed", "timestamp_source": str(source.resolve()), "final_outputs": outputs}
    state = PipelineState(root / "state.json")
    state.mark_complete("export", list(outputs.values()), details)
    result_path = root / "result.json"
    result = _load(result_path) if result_path.is_file() else {}
    result.update({"export_status": "completed", "final_outputs": outputs, "timestamp_source": str(source.resolve())})
    result_path.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return details


def record_export_failure(job_root: str | Path, error: Exception) -> None:
    root = Path(job_root)
    state = PipelineState(root / "state.json")
    state.mark_failed("export", error)
    result_path = root / "result.json"
    result = _load(result_path) if result_path.is_file() else {}
    result.update({"status": "failed", "export_status": "failed", "export_error": str(error)})
    result_path.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
