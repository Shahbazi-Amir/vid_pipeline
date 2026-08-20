"""Targeted ASR retry policy used by the deployable pipeline.

The production service never performs a second full-file transcription for the
normal profiles.  It retries only suspicious segments and records candidates
for the quality/review layers.  This keeps latency bounded without silently
replacing uncertain names/numbers with a second guess.
"""

from __future__ import annotations

import json
import re
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

from vid_pipeline.errors import ExternalToolError
from vid_pipeline.transcribe import TranscriptionConfig, transcribe_audio

PROTECTED = re.compile(r"[0-9۰-۹٠-٩]+|(?:آقای|خانم|دکتر|مهندس|شهید|سردار)\s+\S+")


@dataclass(frozen=True, slots=True)
class TargetedRetryPolicy:
    max_segments: int
    beam_size: int
    low_confidence: float = 0.68
    clip_context_seconds: float = 2.5


PROFILE_RETRY_POLICIES = {
    "fast": TargetedRetryPolicy(max_segments=0, beam_size=5),
    "balanced": TargetedRetryPolicy(max_segments=40, beam_size=10),
    "accurate": TargetedRetryPolicy(max_segments=120, beam_size=12),
}

RetryRunner = Callable[[Path, dict[str, Any], TargetedRetryPolicy, TranscriptionConfig], dict[str, Any]]


def segment_confidence(segment: dict[str, Any]) -> float:
    probabilities = [
        float(word["probability"])
        for word in segment.get("words") or []
        if isinstance(word, dict) and word.get("probability") is not None
    ]
    if probabilities:
        return max(0.0, min(1.0, sum(probabilities) / len(probabilities)))
    return max(0.0, min(1.0, 1.0 + float(segment.get("avg_logprob", -1.0) or -1.0) / 2.0))


def suspicious_for_retry(segment: dict[str, Any], policy: TargetedRetryPolicy) -> bool:
    if not str(segment.get("text", "")).strip():
        return True
    if segment.get("review_flags"):
        return True
    if segment_confidence(segment) < policy.low_confidence:
        return True
    if float(segment.get("no_speech_prob", 0.0) or 0.0) > 0.6:
        return True
    if float(segment.get("avg_logprob", 0.0) or 0.0) < -1.0:
        return True
    return False


def _extract_clip(audio: Path, output: Path, start: float, end: float) -> None:
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        raise ExternalToolError("Required tool 'ffmpeg' was not found in PATH.")
    output.parent.mkdir(parents=True, exist_ok=True)
    completed = subprocess.run(
        [
            ffmpeg,
            "-hide_banner",
            "-loglevel",
            "error",
            "-y",
            "-ss",
            f"{max(0.0, start):.3f}",
            "-i",
            str(audio),
            "-t",
            f"{max(0.2, end - max(0.0, start)):.3f}",
            "-ac",
            "1",
            "-ar",
            "16000",
            "-c:a",
            "pcm_s16le",
            str(output),
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    if completed.returncode != 0:
        raise ExternalToolError(completed.stderr[-1000:] or "targeted clip extraction failed")


def _default_runner(
    clip: Path,
    _segment: dict[str, Any],
    policy: TargetedRetryPolicy,
    config: TranscriptionConfig,
) -> dict[str, Any]:
    result = transcribe_audio(
        clip,
        clip.with_suffix(".retry.json"),
        clip.with_suffix(".retry.md"),
        TranscriptionConfig(
            model=config.model,
            device=config.device,
            compute_type=config.compute_type,
            language=config.language,
            task=config.task,
            beam_size=policy.beam_size,
            vad_filter=False,
            word_timestamps=True,
            condition_on_previous_text=False,
            initial_prompt=config.initial_prompt,
            hotwords=config.hotwords,
            repetition_penalty=max(config.repetition_penalty, 1.05),
            no_repeat_ngram_size=max(config.no_repeat_ngram_size, 3),
            hallucination_silence_threshold=config.hallucination_silence_threshold,
        ),
    )
    rows = result.get("segments") or []
    text = " ".join(str(row.get("text") or "").strip() for row in rows).strip()
    confidence_values = [segment_confidence(row) for row in rows]
    return {
        "text": text,
        "confidence": (
            sum(confidence_values) / len(confidence_values) if confidence_values else 0.0
        ),
        "model": result.get("model"),
        "timing": result.get("timing") or {},
    }


def build_targeted_retry_candidates(
    audio: str | Path,
    raw_result: dict[str, Any],
    *,
    profile: str,
    work_dir: str | Path,
    config: TranscriptionConfig,
    runner: RetryRunner | None = None,
) -> dict[str, Any]:
    """Retry only suspicious ASR segments and return an auditable report.

    Candidates are deliberately *not* auto-promoted to final text.  When the
    retry disagrees on protected names/numbers, the report marks the item for
    review rather than treating a second model pass as ground truth.
    """
    try:
        policy = PROFILE_RETRY_POLICIES[profile]
    except KeyError as exc:
        raise ValueError(f"unknown retry profile: {profile}") from exc
    segments = list(raw_result.get("segments") or [])
    targets = [row for row in segments if suspicious_for_retry(row, policy)][: policy.max_segments]
    report: dict[str, Any] = {
        "schema_version": 1,
        "profile": profile,
        "full_file_additional_passes": 0,
        "targeted_segment_count": len(targets),
        "max_targeted_segments": policy.max_segments,
        "items": [],
    }
    if not targets:
        return report
    audio_path = Path(audio)
    root = Path(work_dir)
    execute = runner or _default_runner
    for index, segment in enumerate(targets, 1):
        start = max(0.0, float(segment.get("start", 0.0)) - policy.clip_context_seconds)
        end = float(segment.get("end", start)) + policy.clip_context_seconds
        clip = root / "targeted-retry" / f"segment-{int(segment.get('id', index)):05d}.wav"
        try:
            if runner is None:
                _extract_clip(audio_path, clip, start, end)
            candidate = execute(clip, segment, policy, config)
            original_text = str(segment.get("text") or "").strip()
            candidate_text = str(candidate.get("text") or "").strip()
            protected_disagreement = set(PROTECTED.findall(original_text)) != set(
                PROTECTED.findall(candidate_text)
            )
            report["items"].append(
                {
                    "segment_id": segment.get("id"),
                    "start": segment.get("start"),
                    "end": segment.get("end"),
                    "original_text": original_text,
                    "original_confidence": round(segment_confidence(segment), 6),
                    "candidate_text": candidate_text,
                    "candidate_confidence": round(float(candidate.get("confidence", 0.0)), 6),
                    "protected_disagreement": protected_disagreement,
                    "requires_review": bool(protected_disagreement or candidate_text != original_text),
                    "status": "candidate_ready",
                }
            )
        except Exception as exc:
            report["items"].append(
                {
                    "segment_id": segment.get("id"),
                    "status": "retry_failed",
                    "error": f"{type(exc).__name__}: {exc}",
                    "requires_review": True,
                }
            )
    report["candidate_count"] = sum(
        item.get("status") == "candidate_ready" for item in report["items"]
    )
    return report


def write_targeted_retry_report(report: dict[str, Any], path: str | Path) -> Path:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return target
