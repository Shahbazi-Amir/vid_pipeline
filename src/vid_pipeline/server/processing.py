"""Canonical media-processing core shared by deployable entry points."""

from __future__ import annotations

import json
import time
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from vid_pipeline.audio import normalize_audio
from vid_pipeline.clean import clean_transcript
from vid_pipeline.models import TranscriptDocument, TranscriptSegment
from vid_pipeline.profiles import DEFAULT_PROFILE, resolve_transcription_model
from vid_pipeline.server.quality_gate import evaluate_transcript_quality
from vid_pipeline.targeted_retry import build_targeted_retry_candidates, write_targeted_retry_report
from vid_pipeline.transcribe import TranscriptionConfig, transcribe_audio

StageCallback = Callable[[str, int], None]


@dataclass(slots=True)
class CoreProcessingResult:
    audio: Path
    audio_quality: Path
    raw_json: Path
    raw_markdown: Path
    machine_markdown: Path
    machine_text: Path
    targeted_retry_report: Path
    raw_payload: dict[str, Any]
    document: TranscriptDocument
    quality_report: dict[str, Any]
    timings: dict[str, float]


def _stage(callback: StageCallback | None, name: str, progress: int) -> None:
    if callback is not None:
        callback(name, progress)


def document_from_raw(job_id: str, language: str, raw: dict[str, Any]) -> TranscriptDocument:
    segments = []
    for index, item in enumerate(raw.get("segments") or [], 1):
        words = item.get("words") or []
        confidence = None
        if words:
            values = [
                float(word.get("probability", 0.0))
                for word in words
                if word.get("probability") is not None
            ]
            confidence = sum(values) / len(values) if values else None
        segments.append(
            TranscriptSegment(
                segment_id=int(item.get("id", index)),
                start=float(item.get("start", 0.0)),
                end=float(item.get("end", 0.0)),
                text=str(item.get("text") or "").strip(),
                confidence=confidence,
                suspicious_flags=list(item.get("review_flags") or []),
                provenance={"source": "raw_asr"},
            )
        )
    return TranscriptDocument(job_id=job_id, language=language, segments=segments)


def process_media_core(
    media: Path,
    job: dict[str, Any],
    work: Path,
    *,
    stage_callback: StageCallback | None = None,
) -> CoreProcessingResult:
    """Normalize, transcribe, retry suspicious spans, clean and quality-check media.

    This is the single deployable processing path.  The worker owns queue/state
    transitions only; ASR/clean/quality policy lives here.  ``stage_callback``
    exposes coarse-grained progress without coupling this core to the database.
    """
    work.mkdir(parents=True, exist_ok=True)
    profile = str(job.get("profile", DEFAULT_PROFILE) or DEFAULT_PROFILE)
    model = resolve_transcription_model(
        profile,
        str(job.get("model", "") or ""),
        allow_local_path=True,
    )
    job["profile"] = profile
    job["model"] = model
    language = str(job.get("language", "fa") or "fa")

    timings: dict[str, float] = {}
    audio = work / "audio.wav"
    audio_quality = work / "audio-quality.json"
    _stage(stage_callback, "normalize_audio", 25)
    started = time.monotonic()
    normalize_audio(
        media,
        audio,
        overwrite=True,
        profile=str(job.get("audio_profile", "safe") or "safe"),
        quality_path=audio_quality,
    )
    timings["normalize_seconds"] = round(time.monotonic() - started, 6)

    raw_json = work / "transcript.raw.json"
    raw_markdown = work / "transcript.raw.md"
    config = TranscriptionConfig(model=model, language=language)
    _stage(stage_callback, "transcribe_primary", 35)
    started = time.monotonic()
    raw_payload = transcribe_audio(audio, raw_json, raw_markdown, config)
    timings["primary_asr_seconds"] = round(time.monotonic() - started, 6)

    _stage(stage_callback, "targeted_retry", 60)
    started = time.monotonic()
    retry_report = build_targeted_retry_candidates(
        audio,
        raw_payload,
        profile=profile,
        work_dir=work,
        config=config,
    )
    retry_path = write_targeted_retry_report(retry_report, work / "targeted-retry-report.json")
    timings["targeted_retry_seconds"] = round(time.monotonic() - started, 6)

    machine_markdown = work / "transcript.machine.md"
    machine_text = work / "transcript.machine.txt"
    _stage(stage_callback, "clean_transcript", 70)
    started = time.monotonic()
    clean_transcript(
        raw_json,
        machine_markdown,
        machine_text,
        title=str(job.get("file_name", "") or ""),
        source_url=str(job.get("source_url", "") or ""),
    )
    timings["clean_seconds"] = round(time.monotonic() - started, 6)

    _stage(stage_callback, "quality_scoring", 78)
    document = document_from_raw(str(job["job_id"]), language, raw_payload)
    quality_report = evaluate_transcript_quality(document, raw_payload)
    quality_report["targeted_retry"] = {
        "full_file_additional_passes": retry_report["full_file_additional_passes"],
        "targeted_segment_count": retry_report["targeted_segment_count"],
        "candidate_count": retry_report.get("candidate_count", 0),
    }

    manifest = {
        "schema_version": 1,
        "job_id": job["job_id"],
        "profile": profile,
        "model": model,
        "language": language,
        "timings": timings,
        "targeted_retry": quality_report["targeted_retry"],
        "quality_gate": {
            "decision": quality_report["decision"],
            "overall_score": quality_report["overall_score"],
        },
    }
    (work / "core-manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    return CoreProcessingResult(
        audio=audio,
        audio_quality=audio_quality,
        raw_json=raw_json,
        raw_markdown=raw_markdown,
        machine_markdown=machine_markdown,
        machine_text=machine_text,
        targeted_retry_report=retry_path,
        raw_payload=raw_payload,
        document=document,
        quality_report=quality_report,
        timings=timings,
    )
