"""Speaker diarization, temporal alignment, and conservative role mapping."""

from __future__ import annotations

import json
import os
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Protocol


class DiarizationError(RuntimeError):
    pass


@dataclass(slots=True)
class SpeakerTurn:
    start: float
    end: float
    speaker: str


@dataclass(slots=True)
class DiarizationConfig:
    enabled: bool = False
    required: bool = False
    num_speakers: int | None = 2
    model: str = "pyannote/speaker-diarization-community-1"
    role_mode: str = "generic"  # generic|host-teacher
    role_overrides: dict[str, str] | None = None
    role_threshold: float = 0.72
    merge_gap_seconds: float = 0.45
    token: str = ""


class DiarizationBackend(Protocol):
    name: str

    def diarize(self, audio: Path, *, num_speakers: int | None) -> list[SpeakerTurn]: ...


class PyannoteDiarizationBackend:
    name = "pyannote.audio"

    def __init__(self, model: str, token: str = "") -> None:
        token = token or os.getenv("HF_TOKEN", "") or os.getenv("HUGGINGFACE_TOKEN", "")
        if not token:
            raise DiarizationError("HF_TOKEN is required for the configured diarization model")
        try:
            from pyannote.audio import Pipeline
        except ImportError as exc:
            raise DiarizationError("pyannote.audio is not installed; install .[diarization]") from exc
        try:
            self.pipeline = Pipeline.from_pretrained(model, token=token)
        except Exception as exc:
            raise DiarizationError(f"could not load diarization model: {type(exc).__name__}") from None

    def diarize(self, audio: Path, *, num_speakers: int | None) -> list[SpeakerTurn]:
        kwargs = {"num_speakers": num_speakers} if num_speakers else {}
        try:
            output = self.pipeline(str(audio), **kwargs)
            annotation = (
                getattr(output, "exclusive_speaker_diarization", None)
                or getattr(output, "speaker_diarization", None)
                or output
            )
            return [
                SpeakerTurn(float(turn.start), float(turn.end), str(speaker))
                for turn, _, speaker in annotation.itertracks(yield_label=True)
            ]
        except Exception as exc:
            raise DiarizationError(f"diarization inference failed: {type(exc).__name__}") from None


def normalize_turns(turns: list[SpeakerTurn]) -> list[SpeakerTurn]:
    valid = sorted((t for t in turns if t.start >= 0 and t.end > t.start), key=lambda t: (t.start, t.end, t.speaker))
    labels: dict[str, str] = {}
    result = []
    for turn in valid:
        labels.setdefault(turn.speaker, f"SPEAKER_{len(labels):02d}")
        result.append(SpeakerTurn(turn.start, turn.end, labels[turn.speaker]))
    return result


def overlap(start: float, end: float, turn: SpeakerTurn) -> float:
    return max(0.0, min(end, turn.end) - max(start, turn.start))


def assign_speaker(start: float, end: float, turns: list[SpeakerTurn]) -> tuple[str, bool]:
    scores: dict[str, float] = {}
    for turn in turns:
        scores[turn.speaker] = scores.get(turn.speaker, 0.0) + overlap(start, end, turn)
    ranked = sorted(scores.items(), key=lambda item: (-item[1], item[0]))
    if not ranked or ranked[0][1] <= 0:
        return "", True
    ambiguous = len(ranked) > 1 and abs(ranked[0][1] - ranked[1][1]) <= 1e-6
    return ranked[0][0], ambiguous


def align_segments(segments: list[dict[str, Any]], turns: list[SpeakerTurn], *, merge_gap: float = 0.45) -> tuple[list[dict[str, Any]], int]:
    """Assign words by overlap and rebuild contiguous speaker utterances."""
    rows: list[dict[str, Any]] = []
    ambiguous = 0
    for segment in segments:
        words = [w for w in (segment.get("words") or []) if w.get("start") is not None and w.get("end") is not None]
        word_text = " ".join(str(w.get("word") or "").strip() for w in words).strip()
        segment_text = " ".join(str(segment.get("text") or "").split())
        # Accuracy/human review may replace the text while retaining the old word
        # timings. Never overwrite that better text with stale Whisper words.
        if words and " ".join(word_text.split()) == segment_text:
            for word in words:
                speaker, unclear = assign_speaker(float(word["start"]), float(word["end"]), turns)
                ambiguous += int(unclear)
                text = str(word.get("word") or "")
                if not text:
                    continue
                row = {"start": float(word["start"]), "end": float(word["end"]), "text": text.strip(), "speaker": speaker}
                if rows and rows[-1]["speaker"] == speaker and row["start"] - rows[-1]["end"] <= merge_gap:
                    joiner = "" if text[:1].isspace() else " "
                    rows[-1]["text"] = (rows[-1]["text"] + joiner + text.strip()).strip()
                    rows[-1]["end"] = row["end"]
                else:
                    rows.append(row)
        else:
            start, end = float(segment["start"]), float(segment["end"])
            boundaries = sorted({start, end, *(t.start for t in turns if start < t.start < end), *(t.end for t in turns if start < t.end < end)})
            # Text cannot be truthfully split without word timings; retain it once and record ambiguity.
            speaker, unclear = assign_speaker(start, end, turns)
            ambiguous += int(unclear or len(boundaries) > 2)
            rows.append({**segment, "speaker": speaker, "speaker_ambiguous": len(boundaries) > 2})
    return rows, ambiguous


def map_roles(segments: list[dict[str, Any]], mode: str, overrides: dict[str, str] | None = None, threshold: float = 0.72) -> dict[str, dict[str, Any]]:
    speakers = sorted({str(s.get("speaker")) for s in segments if s.get("speaker")})
    mapping = {speaker: {"role": "", "confidence": 0.0} for speaker in speakers}
    aliases = {"host": "مجری", "teacher": "استاد"}
    for speaker, role in (overrides or {}).items():
        if speaker in mapping:
            mapping[speaker] = {"role": aliases.get(role, role), "confidence": 1.0, "source": "manual"}
    unresolved = [s for s in speakers if not mapping[s]["role"]]
    if mode == "host-teacher" and len(speakers) == 2 and len(unresolved) == 2:
        stats = {}
        question_words = ("؟", "چرا", "چطور", "چگونه", "چی", "چه ", "آیا", "یعنی", "می‌شود", "ممکن است")
        for speaker in speakers:
            items = [s for s in segments if s.get("speaker") == speaker]
            chars = sum(len(str(s.get("text") or "")) for s in items)
            questions = sum(any(marker in str(s.get("text") or "") for marker in question_words) for s in items)
            stats[speaker] = (questions / max(1, len(items))) + (1 / max(1, chars))
        ordered = sorted(speakers, key=lambda s: (-stats[s], s))
        difference = abs(stats[ordered[0]] - stats[ordered[1]])
        confidence = min(0.95, 0.5 + difference * 2.5)
        if confidence >= threshold:
            mapping[ordered[0]] = {"role": "مجری", "confidence": round(confidence, 3), "source": "heuristic"}
            mapping[ordered[1]] = {"role": "استاد", "confidence": round(confidence, 3), "source": "heuristic"}
    return mapping


def apply_roles(segments: list[dict[str, Any]], mapping: dict[str, dict[str, Any]]) -> None:
    for segment in segments:
        item = mapping.get(str(segment.get("speaker")), {})
        if item.get("role"):
            segment["speaker_role"] = item["role"]
            segment["speaker_role_confidence"] = item["confidence"]


def run_diarization(audio: Path, segments: list[dict[str, Any]], config: DiarizationConfig, *, backend: DiarizationBackend | None = None, output: Path | None = None) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    started = time.monotonic()
    backend = backend or PyannoteDiarizationBackend(config.model, config.token)
    turns = normalize_turns(backend.diarize(audio, num_speakers=config.num_speakers))
    if not turns:
        raise DiarizationError("diarization returned zero speakers")
    aligned, ambiguous = align_segments(segments, turns, merge_gap=config.merge_gap_seconds)
    mapping = map_roles(aligned, config.role_mode, config.role_overrides, config.role_threshold)
    apply_roles(aligned, mapping)
    durations: dict[str, float] = {}
    for turn in turns:
        durations[turn.speaker] = durations.get(turn.speaker, 0.0) + turn.end - turn.start
    report = {
        "schema_version": 1, "status": "completed", "backend": backend.name,
        "model": config.model, "requested_speaker_count": config.num_speakers,
        "detected_speaker_count": len(durations), "speaker_durations": durations,
        "speaker_turn_count": len(turns), "ambiguous_assignments": ambiguous,
        "role_mapping": mapping, "runtime_seconds": round(time.monotonic() - started, 3),
        "config": {k: v for k, v in asdict(config).items() if k != "token"},
        "turns": [asdict(t) for t in turns],
    }
    if output:
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return aligned, report


def parse_role_overrides(values: list[str]) -> dict[str, str]:
    result = {}
    for value in values:
        if "=" not in value:
            raise ValueError("speaker role override must use SPEAKER_00=role")
        speaker, role = (part.strip() for part in value.split("=", 1))
        if not speaker or not role:
            raise ValueError("speaker role override must use SPEAKER_00=role")
        result[speaker] = role
    return result
