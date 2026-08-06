"""Speaker diarization, temporal alignment, and conservative role mapping."""

from __future__ import annotations

import json
import time
from collections import Counter
from dataclasses import asdict, dataclass
from itertools import permutations
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
    backend: str = "pyannote-community-1"
    model_cache_dir: Path | None = None
    role_mode: str = "generic"  # generic|host-teacher
    role_overrides: dict[str, str] | None = None
    role_threshold: float = 0.72
    merge_gap_seconds: float = 0.45
    effective_min_duration_seconds: float = 2.0
    effective_min_turns: int = 1
    effective_min_fraction: float = 0.01
    aligned_min_word_count: int = 3
    aligned_min_duration_seconds: float = 1.0
    aligned_min_segments: int = 1
    aligned_min_fraction: float = 0.005
    smoothing_enabled: bool = True
    micro_turn_max_duration_seconds: float = 1.25
    micro_turn_max_words: int = 3
    strong_micro_island_max_duration_seconds: float = 0.90
    strong_micro_island_max_words: int = 2
    smoothing_max_gap_seconds: float = 0.25
    smoothing_min_overlap_margin: float = 0.20
    minimum_export_turn_span_seconds: float = 0.10
    reproducibility_attempts: int = 3
    suspicious_minority_fraction: float = 0.03
    stability_min_timeline_agreement: float = 0.90
    stability_max_turn_count_fraction: float = 0.35


class DiarizationBackend(Protocol):
    name: str

    def diarize(self, audio: Path, *, num_speakers: int | None) -> list[SpeakerTurn]: ...


def _file_manifest(path: Path, *, expected_sha256: str = "") -> dict[str, Any]:
    import hashlib

    stat = path.stat()
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    actual = digest.hexdigest()
    return {
        "path": str(path.resolve()),
        "filename": path.name,
        "size": stat.st_size,
        "sha256": actual,
        "expected_sha256": expected_sha256,
        "integrity_ok": not expected_sha256 or actual == expected_sha256,
    }


def _audio_manifest(path: Path) -> dict[str, Any]:
    import soundfile as sf

    info = sf.info(path)
    return {
        **_file_manifest(path),
        "sample_rate": info.samplerate,
        "channels": info.channels,
        "sample_count": info.frames,
        "duration": info.duration,
    }


def _turn_summary(turns: list[SpeakerTurn], run_index: int) -> dict[str, Any]:
    durations: Counter[str] = Counter()
    counts: Counter[str] = Counter()
    for turn in turns:
        durations[turn.speaker] += max(0.0, turn.end - turn.start)
        counts[turn.speaker] += 1
    total = sum(durations.values())
    minority = min(durations.values(), default=0.0) / total if total else 0.0
    ordered = sorted(turns, key=lambda turn: (turn.start, turn.end, turn.speaker))
    return {
        "run_index": run_index,
        "raw_turn_count": len(turns),
        "raw_speaker_count": len(durations),
        "per_speaker_raw_duration": dict(durations),
        "per_speaker_raw_turn_count": dict(counts),
        "minority_speaker_fraction": minority,
        "speaker_switch_count": _raw_speaker_switches(ordered),
        "first_raw_turns": [asdict(turn) for turn in ordered[:5]],
        "last_raw_turns": [asdict(turn) for turn in ordered[-5:]],
    }


def _raw_speaker_switches(turns: list[SpeakerTurn]) -> int:
    labels = [turn.speaker for turn in turns]
    return sum(left != right for left, right in zip(labels, labels[1:]))


def compare_diarization_runs(
    left: list[SpeakerTurn], right: list[SpeakerTurn]
) -> dict[str, Any]:
    """Compare timelines while treating speaker-label permutations as equivalent."""

    left_labels = sorted({turn.speaker for turn in left})
    right_labels = sorted({turn.speaker for turn in right})
    boundaries = sorted({value for turn in left + right for value in (turn.start, turn.end)})
    intervals = list(zip(boundaries, boundaries[1:]))
    total = sum(end - start for start, end in intervals)

    def active(turns: list[SpeakerTurn], midpoint: float) -> set[str]:
        return {turn.speaker for turn in turns if turn.start <= midpoint < turn.end}

    best = 0.0
    best_mapping: dict[str, str] = {}
    if len(left_labels) == len(right_labels):
        for permuted in permutations(right_labels):
            mapping = dict(zip(permuted, left_labels))
            agreed = 0.0
            for start, end in intervals:
                midpoint = (start + end) / 2
                lhs = active(left, midpoint)
                rhs = {mapping[label] for label in active(right, midpoint)}
                if lhs == rhs:
                    agreed += end - start
            if agreed > best:
                best, best_mapping = agreed, mapping
    agreement = best / total if total else 1.0
    left_summary = _turn_summary(left, 0)
    right_summary = _turn_summary(right, 0)
    turn_difference = abs(len(left) - len(right))
    turn_fraction = turn_difference / max(len(left), len(right), 1)
    return {
        "speaker_count_agreement": len(left_labels) == len(right_labels),
        "turn_count_difference": turn_difference,
        "turn_count_difference_fraction": turn_fraction,
        "speaker_switch_count_difference": abs(
            left_summary["speaker_switch_count"] - right_summary["speaker_switch_count"]
        ),
        "minority_fraction_difference": abs(
            left_summary["minority_speaker_fraction"]
            - right_summary["minority_speaker_fraction"]
        ),
        "timeline_assignment_agreement": agreement,
        "label_mapping": best_mapping,
    }


def select_diarization_consensus(
    attempts: list[list[SpeakerTurn]], config: DiarizationConfig
) -> tuple[int, dict[str, Any]]:
    if not attempts:
        raise DiarizationError("diarization reproducibility check received no attempts")
    comparisons: list[dict[str, Any]] = []
    scores = [0.0] * len(attempts)
    strong_pairs: list[tuple[int, int]] = []
    for left_index in range(len(attempts)):
        for right_index in range(left_index + 1, len(attempts)):
            comparison = compare_diarization_runs(attempts[left_index], attempts[right_index])
            severe = (
                not comparison["speaker_count_agreement"]
                or comparison["timeline_assignment_agreement"]
                < config.stability_min_timeline_agreement
                or comparison["turn_count_difference_fraction"]
                > config.stability_max_turn_count_fraction
            )
            comparison.update({"left": left_index + 1, "right": right_index + 1, "severe": severe})
            comparisons.append(comparison)
            scores[left_index] += comparison["timeline_assignment_agreement"]
            scores[right_index] += comparison["timeline_assignment_agreement"]
            if not severe:
                strong_pairs.append((left_index, right_index))
    if len(attempts) > 1 and not strong_pairs:
        agreements = [item["timeline_assignment_agreement"] for item in comparisons]
        raise DiarizationError(
            "Diarization reproducibility check failed: "
            f"attempts={len(attempts)} severe_disagreement=true "
            f"best_pair_agreement={max(agreements, default=0.0):.6f} "
            f"worst_pair_agreement={min(agreements, default=0.0):.6f}"
        )
    selected = max(range(len(attempts)), key=lambda index: (scores[index], -index))
    if strong_pairs and not any(selected in pair for pair in strong_pairs):
        selected = strong_pairs[0][0]
    values = [comparison["timeline_assignment_agreement"] for comparison in comparisons]
    return selected, {
        "attempt_count": len(attempts),
        "stable": not comparisons or all(not item["severe"] for item in comparisons),
        "best_pair_agreement": max(values, default=1.0),
        "worst_pair_agreement": min(values, default=1.0),
        "selected_attempt": selected + 1,
        "selection_reason": "single_run" if len(attempts) == 1 else "highest_cross_run_agreement",
        "comparisons": comparisons,
    }


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
    evidence = _speaker_evidence(start, end, turns)
    return str(evidence["speaker"]), bool(evidence["ambiguous"])


def _speaker_evidence(
    start: float, end: float, turns: list[SpeakerTurn]
) -> dict[str, Any]:
    scores: dict[str, float] = {}
    shortest_overlapping_turn: dict[str, float] = {}
    for turn in turns:
        amount = overlap(start, end, turn)
        scores[turn.speaker] = scores.get(turn.speaker, 0.0) + amount
        if amount > 0:
            duration = turn.end - turn.start
            shortest_overlapping_turn[turn.speaker] = min(
                duration, shortest_overlapping_turn.get(turn.speaker, duration)
            )
    # Overlapping timelines can contain a short turn nested inside a longer turn.
    # Prefer the more temporally specific turn when overlap scores are tied.
    ranked = sorted(
        scores.items(),
        key=lambda item: (
            -item[1], shortest_overlapping_turn.get(item[0], float("inf")), item[0]
        ),
    )
    if not ranked or ranked[0][1] <= 0:
        return {
            "speaker": "", "winning_overlap": 0.0, "runner_up_overlap": 0.0,
            "overlap_margin": 0.0, "ambiguous": True,
            "supporting_raw_turn_duration": 0.0,
        }
    ambiguous = len(ranked) > 1 and abs(ranked[0][1] - ranked[1][1]) <= 1e-6
    winner, winning_overlap = ranked[0]
    runner_up_overlap = ranked[1][1] if len(ranked) > 1 else 0.0
    margin = (winning_overlap - runner_up_overlap) / max(winning_overlap, 1e-9)
    return {
        "speaker": winner,
        "winning_overlap": winning_overlap,
        "runner_up_overlap": runner_up_overlap,
        "overlap_margin": margin,
        "ambiguous": ambiguous,
        "supporting_raw_turn_duration": shortest_overlapping_turn.get(winner, 0.0),
    }


def _interval_overlap_duration(
    start: float, end: float, turns: list[SpeakerTurn]
) -> float:
    """Return union overlap so overlapping same-speaker turns are not double-counted."""

    intervals = sorted(
        (max(start, turn.start), min(end, turn.end))
        for turn in turns
        if overlap(start, end, turn) > 0
    )
    total = 0.0
    current_start: float | None = None
    current_end: float | None = None
    for interval_start, interval_end in intervals:
        if current_start is None:
            current_start, current_end = interval_start, interval_end
        elif interval_start <= current_end:
            current_end = max(current_end, interval_end)
        else:
            total += current_end - current_start
            current_start, current_end = interval_start, interval_end
    if current_start is not None and current_end is not None:
        total += current_end - current_start
    return total


_CLOSING_PUNCTUATION = frozenset(".,،:;؛!؟?)]}")
_OPENING_PUNCTUATION = frozenset("([{«")


def join_word_tokens(tokens: list[str]) -> str:
    """Join Whisper word tokens while preserving Persian ZWNJ and punctuation."""

    result = ""
    for raw in tokens:
        if not raw:
            continue
        token = raw.strip(" \t\r\n")
        if not token:
            continue
        if not result:
            result = token
        elif token[0] in _CLOSING_PUNCTUATION or result[-1] in _OPENING_PUNCTUATION:
            result += token
        else:
            # A leading Whisper space is a word boundary, not an instruction to
            # concatenate. Tokens without it still need a boundary for Persian
            # and other whitespace-delimited languages.
            result += " " + token
    return result.strip()


def align_segments(segments: list[dict[str, Any]], turns: list[SpeakerTurn], *, merge_gap: float = 0.45) -> tuple[list[dict[str, Any]], int]:
    """Assign words by overlap and rebuild contiguous speaker utterances."""
    rows: list[dict[str, Any]] = []
    ambiguous = 0
    for segment in segments:
        words = [w for w in (segment.get("words") or []) if w.get("start") is not None and w.get("end") is not None]
        word_text = join_word_tokens([str(w.get("word") or "") for w in words])
        segment_text = " ".join(str(segment.get("text") or "").split())
        # Accuracy/human review may replace the text while retaining the old word
        # timings. Never overwrite that better text with stale Whisper words.
        if words and " ".join(word_text.split()) == segment_text:
            for word in words:
                evidence = _speaker_evidence(float(word["start"]), float(word["end"]), turns)
                speaker, unclear = str(evidence["speaker"]), bool(evidence["ambiguous"])
                ambiguous += int(unclear)
                text = str(word.get("word") or "")
                if not text:
                    continue
                row = {"start": float(word["start"]), "end": float(word["end"]), "text": text.strip(), "speaker": speaker,
                       "speaker_evidence": evidence, "aligned_word_count": 1}
                if (
                    rows
                    and "speaker_evidence" in rows[-1]
                    and rows[-1]["speaker"] == speaker
                    and row["start"] - rows[-1]["end"] <= merge_gap
                ):
                    rows[-1]["text"] = join_word_tokens([rows[-1]["text"], text])
                    rows[-1]["end"] = row["end"]
                    previous = rows[-1]["speaker_evidence"]
                    previous["winning_overlap"] += evidence["winning_overlap"]
                    previous["runner_up_overlap"] += evidence["runner_up_overlap"]
                    previous["overlap_margin"] = (
                        (previous["winning_overlap"] - previous["runner_up_overlap"])
                        / max(previous["winning_overlap"], 1e-9)
                    )
                    previous["ambiguous"] = previous["ambiguous"] or unclear
                    previous["supporting_raw_turn_duration"] = min(
                        previous["supporting_raw_turn_duration"] or float("inf"),
                        evidence["supporting_raw_turn_duration"] or float("inf"),
                    )
                    rows[-1]["aligned_word_count"] += 1
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


def _speaker_switches(rows: list[dict[str, Any]]) -> int:
    speakers = [str(row.get("speaker") or "") for row in rows]
    return sum(current != previous for previous, current in zip(speakers, speakers[1:]))


_PROTECTED_SHORT_REPLIES = frozenset({
    "بله", "نه", "آره", "اره", "خب", "درسته", "درست", "دقیقاً", "دقیقا",
    "حتماً", "حتما", "البته", "باشه", "ممنون",
})
_SHORT_REPLY_TRIM = " \t\r\n.,،:;؛!؟?…«»()[]{}\"'"


def _normalized_short_reply(text: str) -> str:
    value = " ".join(str(text or "").strip().split()).strip(_SHORT_REPLY_TRIM)
    return value.replace("ي", "ی").replace("ك", "ک")


def _is_protected_short_reply(text: str) -> bool:
    return _normalized_short_reply(text) in _PROTECTED_SHORT_REPLIES


def smooth_speaker_turns(
    rows: list[dict[str, Any]], config: DiarizationConfig
) -> tuple[list[dict[str, Any]], dict[str, int]]:
    """Conservatively remove false same-speaker sandwich micro-turns."""

    smoothed = [dict(row) for row in rows]
    before = len(smoothed)
    switches_before = _speaker_switches(smoothed)
    merged = preserved = 0
    weak_merged = strong_merged = protected_preserved = 0
    if config.smoothing_enabled:
        index = 1
        while index < len(smoothed) - 1:
            previous, candidate, following = smoothed[index - 1:index + 2]
            duration = max(0.0, float(candidate["end"]) - float(candidate["start"]))
            word_count = int(
                candidate.get("aligned_word_count")
                or len(str(candidate.get("text") or "").split())
            )
            evidence = candidate.get("speaker_evidence") or {}
            same_speaker_sandwich = (
                previous.get("speaker") == following.get("speaker")
                and candidate.get("speaker") != previous.get("speaker")
            )
            local = (
                float(candidate["start"]) - float(previous["end"])
                <= config.smoothing_max_gap_seconds
                and float(following["start"]) - float(candidate["end"])
                <= config.smoothing_max_gap_seconds
            )
            micro = (
                duration <= config.micro_turn_max_duration_seconds
                and word_count <= config.micro_turn_max_words
            )
            near_zero = duration < config.minimum_export_turn_span_seconds
            weak = bool(evidence.get("ambiguous", True)) or float(
                evidence.get("overlap_margin", 0.0)
            ) < config.smoothing_min_overlap_margin
            boundary = str(previous.get("text") or "").rstrip().endswith(
                tuple(".!؟?")
            ) or str(candidate.get("text") or "").rstrip().endswith(tuple(".!؟?"))
            protected_reply = _is_protected_short_reply(str(candidate.get("text") or ""))
            raw_support = float(evidence.get("supporting_raw_turn_duration", 0.0) or 0.0)
            strong_fragmentary_island = (
                duration <= config.strong_micro_island_max_duration_seconds
                and word_count <= config.strong_micro_island_max_words
                and raw_support > 0.0
                and raw_support <= config.strong_micro_island_max_duration_seconds
                and not protected_reply
                and not boundary
            )
            eligible = same_speaker_sandwich and local and micro
            should_merge = (
                eligible
                and not protected_reply
                and (near_zero or not boundary)
                and (weak or strong_fragmentary_island)
            )
            if should_merge:
                previous["text"] = join_word_tokens([
                    str(previous.get("text") or ""),
                    str(candidate.get("text") or ""),
                    str(following.get("text") or ""),
                ])
                previous["end"] = following["end"]
                previous["aligned_word_count"] = sum(
                    int(
                        row.get("aligned_word_count")
                        or len(str(row.get("text") or "").split())
                    )
                    for row in (previous, candidate, following)
                )
                smoothed[index - 1:index + 2] = [previous]
                merged += 1
                if strong_fragmentary_island and not weak:
                    strong_merged += 1
                else:
                    weak_merged += 1
                index = max(1, index - 1)
                continue
            if eligible:
                preserved += 1
                if protected_reply:
                    protected_preserved += 1
            index += 1
    return smoothed, {
        "pre_smoothing_segments": before,
        "post_smoothing_segments": len(smoothed),
        "speaker_switches_before": switches_before,
        "speaker_switches_after": _speaker_switches(smoothed),
        "micro_turns_merged": merged,
        "weak_micro_turns_merged": weak_merged,
        "strong_micro_islands_merged": strong_merged,
        "protected_short_replies_preserved": protected_preserved,
        "micro_turns_preserved": preserved,
    }


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


def _aligned_counts(rows: list[dict[str, Any]], config: DiarizationConfig) -> dict[str, Any]:
    segments = Counter(str(row.get("speaker")) for row in rows if row.get("speaker"))
    words: Counter[str] = Counter()
    durations: Counter[str] = Counter()
    for row in rows:
        speaker = str(row.get("speaker") or "")
        if not speaker:
            continue
        words[speaker] += int(
            row.get("aligned_word_count")
            or len(row.get("words") or [])
            or len(str(row.get("text") or "").split())
        )
        durations[speaker] += max(0.0, float(row["end"]) - float(row["start"]))
    total = sum(durations.values())
    effective = sorted(
        speaker for speaker in segments
        if words[speaker] >= config.aligned_min_word_count
        and durations[speaker] >= config.aligned_min_duration_seconds
        and segments[speaker] >= config.aligned_min_segments
        and (durations[speaker] / total if total else 0.0) >= config.aligned_min_fraction
    )
    return {
        "speaker_count": len(segments),
        "effective_speakers": effective,
        "effective_speaker_count": len(effective),
        "segment_counts": dict(segments),
        "word_counts": dict(words),
        "durations": dict(durations),
        "speaker_switch_count": _speaker_switches(rows),
    }


def run_diarization(audio: Path, segments: list[dict[str, Any]], config: DiarizationConfig, *, backend: DiarizationBackend | None = None, output: Path | None = None) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    started = time.monotonic()
    if backend is None:
        from vid_pipeline.pyannote_diarization import PyannoteDiarizationBackend

        backend = PyannoteDiarizationBackend()
    attempts = [backend.diarize(audio, num_speakers=config.num_speakers)]
    first_summary = _turn_summary(attempts[0], 1)
    suspicious = (
        config.num_speakers is not None
        and (
            first_summary["raw_speaker_count"] < config.num_speakers
            or first_summary["minority_speaker_fraction"]
            < config.suspicious_minority_fraction
        )
    )
    if suspicious:
        for _ in range(1, max(1, config.reproducibility_attempts)):
            attempts.append(backend.diarize(audio, num_speakers=config.num_speakers))
    attempt_summaries = [_turn_summary(turns, index + 1) for index, turns in enumerate(attempts)]
    try:
        selected_attempt, reproducibility = select_diarization_consensus(attempts, config)
    except DiarizationError:
        if output:
            output.parent.mkdir(parents=True, exist_ok=True)
            (output.parent / "diarization-reproducibility.json").write_text(
                json.dumps({"attempts": attempt_summaries, "severe_disagreement": True}, indent=2)
                + "\n",
                encoding="utf-8",
            )
        raise
    raw_turns = attempts[selected_attempt]
    turns = normalize_turns(raw_turns)
    if not turns:
        raise DiarizationError("diarization returned zero speakers")
    aligned_original, ambiguous = align_segments(
        segments, turns, merge_gap=config.merge_gap_seconds
    )
    durations: dict[str, float] = {}
    turn_counts: Counter[str] = Counter()
    for turn in turns:
        durations[turn.speaker] = durations.get(turn.speaker, 0.0) + turn.end - turn.start
        turn_counts[turn.speaker] += 1
    total_duration = sum(durations.values())
    effective = sorted(
        speaker for speaker, duration in durations.items()
        if duration >= config.effective_min_duration_seconds
        and turn_counts[speaker] >= config.effective_min_turns
        and (duration / total_duration if total_duration else 0) >= config.effective_min_fraction
    )
    pre_smoothing = _aligned_counts(aligned_original, config)
    smoothed_candidate, smoothing_diagnostics = smooth_speaker_turns(aligned_original, config)
    post_smoothing_candidate = _aligned_counts(smoothed_candidate, config)
    collapse = (
        config.num_speakers is not None
        and pre_smoothing["effective_speaker_count"] >= config.num_speakers
        and post_smoothing_candidate["effective_speaker_count"] < config.num_speakers
    )
    aligned = aligned_original if collapse else smoothed_candidate
    post_smoothing = _aligned_counts(aligned, config)
    smoothing_diagnostics.update({
        "smoothing_accepted": not collapse,
        "smoothing_rollback": collapse,
        "smoothing_rollback_reason": "speaker_collapse" if collapse else "",
        "candidate_post_smoothing_effective_speaker_count": (
            post_smoothing_candidate["effective_speaker_count"]
        ),
    })
    aligned_segment_counts = Counter(
        str(segment.get("speaker")) for segment in aligned if segment.get("speaker")
    )
    aligned_word_counts = Counter()
    aligned_text_durations: dict[str, float] = {}
    unassigned_words = 0
    for segment in aligned:
        count = len(segment.get("words") or []) or len(str(segment.get("text") or "").split())
        speaker = str(segment.get("speaker") or "")
        if speaker:
            aligned_word_counts[speaker] += count
            aligned_text_durations[speaker] = (
                aligned_text_durations.get(speaker, 0.0)
                + max(0.0, float(segment["end"]) - float(segment["start"]))
            )
        else:
            unassigned_words += count
    words = [
        word
        for segment in segments
        for word in (segment.get("words") or [])
        if word.get("start") is not None and word.get("end") is not None
    ]
    total_aligned_duration = sum(aligned_text_durations.values())
    speaker_diagnostics: dict[str, dict[str, Any]] = {}
    for speaker in sorted(durations):
        speaker_turns = [turn for turn in turns if turn.speaker == speaker]
        word_overlap_duration = sum(
            _interval_overlap_duration(float(word["start"]), float(word["end"]), speaker_turns)
            for word in words
        )
        overlapping_words = sum(
            _interval_overlap_duration(float(word["start"]), float(word["end"]), speaker_turns) > 0
            for word in words
        )
        segment_overlap_duration = sum(
            _interval_overlap_duration(float(segment["start"]), float(segment["end"]), speaker_turns)
            for segment in segments
        )
        overlapping_segments = sum(
            _interval_overlap_duration(float(segment["start"]), float(segment["end"]), speaker_turns) > 0
            for segment in segments
        )
        speaker_diagnostics[speaker] = {
            "raw_duration": round(durations[speaker], 6),
            "raw_turns": turn_counts[speaker],
            "word_overlap_duration": round(word_overlap_duration, 6),
            "word_overlap_count": overlapping_words,
            "segment_overlap_duration": round(segment_overlap_duration, 6),
            "segment_overlap_count": overlapping_segments,
            "aligned_words": aligned_word_counts[speaker],
            "aligned_segments": aligned_segment_counts[speaker],
            "aligned_text_duration": round(aligned_text_durations.get(speaker, 0.0), 6),
            "aligned_voiced_fraction": round(
                aligned_text_durations.get(speaker, 0.0) / total_aligned_duration
                if total_aligned_duration else 0.0,
                6,
            ),
            "coverage_ratio": round(
                word_overlap_duration / durations[speaker] if durations[speaker] else 0.0, 6
            ),
        }
    aligned_effective = sorted(
        speaker
        for speaker in durations
        if aligned_word_counts[speaker] >= config.aligned_min_word_count
        and aligned_text_durations.get(speaker, 0.0) >= config.aligned_min_duration_seconds
        and aligned_segment_counts[speaker] >= config.aligned_min_segments
        and (
            aligned_text_durations.get(speaker, 0.0) / total_aligned_duration
            if total_aligned_duration else 0.0
        ) >= config.aligned_min_fraction
    )
    mapping = map_roles(
        aligned,
        config.role_mode if len(aligned_effective) >= 2 else "generic",
        config.role_overrides,
        config.role_threshold,
    )
    apply_roles(aligned, mapping)
    quality_gate_passed = (
        config.num_speakers is None
        or (
            len(effective) >= config.num_speakers
            and len(aligned_effective) >= config.num_speakers
        )
    )
    report = {
        "schema_version": 1,
        "status": "failed" if config.required and not quality_gate_passed else "completed",
        "backend": backend.name,
        "models": (
            {"pipeline": str(backend.model_id)}
            if getattr(backend, "model_id", "")
            else {}
        ),
        "requested_speaker_count": config.num_speakers,
        "raw_turn_count": len(raw_turns),
        "raw_speakers": sorted({turn.speaker for turn in raw_turns}),
        "normalized_turn_count": len(turns),
        "normalized_speakers": sorted(durations),
        "raw_stage": {
            "speaker_count": attempt_summaries[selected_attempt]["raw_speaker_count"],
            "turn_count": attempt_summaries[selected_attempt]["raw_turn_count"],
            "speaker_switch_count": attempt_summaries[selected_attempt]["speaker_switch_count"],
            "per_speaker_duration": attempt_summaries[selected_attempt][
                "per_speaker_raw_duration"
            ],
            "per_speaker_turn_count": attempt_summaries[selected_attempt][
                "per_speaker_raw_turn_count"
            ],
        },
        "normalized_stage": {
            "speaker_count": len(durations),
            "effective_speaker_count": len(effective),
            "turn_count": len(turns),
            "speaker_switch_count": _raw_speaker_switches(turns),
            "per_speaker_duration": durations,
            "per_speaker_turn_count": dict(turn_counts),
        },
        "detected_speaker_count": len(durations), "speaker_durations": durations,
        "speaker_turn_count": len(turns), "speaker_turn_counts": dict(turn_counts),
        "aligned_segment_counts": dict(aligned_segment_counts),
        "aligned_word_counts": dict(aligned_word_counts),
        "unassigned_word_count": unassigned_words,
        "ambiguous_word_count": ambiguous,
        "ambiguous_assignments": ambiguous,
        **smoothing_diagnostics,
        "pre_smoothing_speaker_count": pre_smoothing["speaker_count"],
        "pre_smoothing_effective_speaker_count": pre_smoothing["effective_speaker_count"],
        "post_smoothing_speaker_count": post_smoothing["speaker_count"],
        "post_smoothing_effective_speaker_count": post_smoothing["effective_speaker_count"],
        "pre_smoothing": pre_smoothing,
        "post_smoothing": post_smoothing,
        "effective_speakers": effective,
        "effective_speaker_count": len(effective),
        "raw_effective_speakers": effective,
        "raw_effective_speaker_count": len(effective),
        "aligned_effective_speakers": aligned_effective,
        "aligned_effective_speaker_count": len(aligned_effective),
        "speakers": speaker_diagnostics,
        "quality_gate_passed": quality_gate_passed,
        "quality_warning": (
            "" if quality_gate_passed
            else "Diarization quality gate failed after alignment: "
            f"requested={config.num_speakers} raw_effective={len(effective)} "
            f"aligned_effective={len(aligned_effective)}"
        ),
        "role_mapping": mapping, "runtime_seconds": round(time.monotonic() - started, 3),
        "reproducibility": reproducibility,
        "diarization_attempts": attempt_summaries,
        "config": {
            key: str(value) if isinstance(value, Path) else value
            for key, value in asdict(config).items()
        },
        "turns": [asdict(t) for t in turns],
    }
    if output:
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        for index, attempt in enumerate(attempts, 1):
            (output.parent / f"raw-turns-attempt-{index}.json").write_text(
                json.dumps([asdict(turn) for turn in attempt], ensure_ascii=False, indent=2)
                + "\n",
                encoding="utf-8",
            )
        (output.parent / "diarization-reproducibility.json").write_text(
            json.dumps({**reproducibility, "attempts": attempt_summaries}, indent=2) + "\n",
            encoding="utf-8",
        )
        (output.parent / "alignment-pre-smoothing.json").write_text(
            json.dumps(aligned_original, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
        (output.parent / "alignment-post-smoothing.json").write_text(
            json.dumps(aligned, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
        if audio.is_file():
            (output.parent / "audio-manifest.json").write_text(
                json.dumps(_audio_manifest(audio), indent=2) + "\n", encoding="utf-8"
            )
    print(
        "diarization diagnostics: "
        f"requested={config.num_speakers} raw_speakers={len(report['raw_speakers'])} "
        f"raw_turns={len(raw_turns)} normalized_speakers={len(durations)} "
        f"raw_effective={len(effective)} aligned_speakers={len(aligned_segment_counts)} "
        f"aligned_effective={len(aligned_effective)} "
        f"ambiguous_words={ambiguous} durations={durations}"
    )
    if (
        config.required
        and config.num_speakers is not None
        and (
            len(effective) < config.num_speakers
            or len(aligned_effective) < config.num_speakers
        )
    ):
        raise DiarizationError(
            "Diarization quality gate failed after alignment: "
            f"requested={config.num_speakers} raw_effective={len(effective)} "
            f"aligned_effective={len(aligned_effective)}"
        )
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
