"""Speaker diarization, temporal alignment, and conservative role mapping."""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import sys
import tarfile
import tempfile
import time
import urllib.request
from collections import Counter
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
    backend: str = "sherpa-onnx"
    segmentation_model: str = "segmentation-3.0-int8"
    embedding_model: str = "3dspeaker-eres2net-base"
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
    smoothing_max_gap_seconds: float = 0.25
    smoothing_min_overlap_margin: float = 0.20
    minimum_export_turn_span_seconds: float = 0.10
    clustering_threshold: float = 0.5
    min_duration_on: float = 0.3
    min_duration_off: float = 0.5


@dataclass(frozen=True, slots=True)
class ModelArtifact:
    name: str
    url: str
    sha256: str
    required_file: str
    file_sha256: str
    archive: bool = False


SEGMENTATION_ARTIFACT = ModelArtifact(
    name="sherpa-onnx-pyannote-segmentation-3-0",
    url=("https://github.com/k2-fsa/sherpa-onnx/releases/download/"
         "speaker-segmentation-models/sherpa-onnx-pyannote-segmentation-3-0.tar.bz2"),
    sha256="24615ee884c897d9d2ba09bb4d30da6bb1b15e685065962db5b02e76e4996488",
    required_file="model.int8.onnx",
    file_sha256="d582f4b4c6b48205de7e0643c57df0df5615a3c176189be3fc461e9d18827b5d",
    archive=True,
)
EMBEDDING_ARTIFACT = ModelArtifact(
    name="3dspeaker-eres2net-base",
    url=("https://github.com/k2-fsa/sherpa-onnx/releases/download/"
         "speaker-recongition-models/3dspeaker_speech_eres2net_base_sv_zh-cn_3dspeaker_16k.onnx"),
    sha256="1a331345f04805badbb495c775a6ddffcdd1a732567d5ec8b3d5749e3c7a5e4b",
    required_file="3dspeaker_speech_eres2net_base_sv_zh-cn_3dspeaker_16k.onnx",
    file_sha256="1a331345f04805badbb495c775a6ddffcdd1a732567d5ec8b3d5749e3c7a5e4b",
)


class DiarizationModelManager:
    def __init__(self, cache_dir: Path | None = None, *, opener: Any = None) -> None:
        configured = os.getenv("VID_PIPELINE_DIARIZATION_CACHE", "").strip()
        self.cache_dir = Path(cache_dir or configured or Path.home() / ".cache/vid-pipeline/diarization")
        self.opener = opener or urllib.request.urlopen

    @staticmethod
    def _digest(path: Path) -> str:
        digest = hashlib.sha256()
        with path.open("rb") as stream:
            for chunk in iter(lambda: stream.read(1024 * 1024), b""):
                digest.update(chunk)
        return digest.hexdigest()

    @staticmethod
    def _safe_extract(archive: Path, target: Path) -> None:
        with tarfile.open(archive, "r:bz2") as bundle:
            root = target.resolve()
            for member in bundle.getmembers():
                if member.issym() or member.islnk():
                    raise DiarizationError("model archive contains a link")
                destination = (target / member.name).resolve()
                if root not in destination.parents and destination != root:
                    raise DiarizationError("model archive contains an unsafe path")
            if sys.version_info >= (3, 12):
                bundle.extractall(target, filter="data")
            else:  # Python 3.10/3.11 have no extraction filter API.
                bundle.extractall(target)

    def _download(self, artifact: ModelArtifact, target: Path) -> None:
        part = target.with_suffix(target.suffix + ".part")
        part.unlink(missing_ok=True)
        print(f"downloading diarization model: {artifact.url}")
        try:
            request = urllib.request.Request(artifact.url, headers={"User-Agent": "vid-pipeline"})
            with self.opener(request, timeout=180) as response, part.open("wb") as output:
                shutil.copyfileobj(response, output, length=1024 * 1024)
            if self._digest(part) != artifact.sha256:
                raise DiarizationError(f"checksum mismatch for {artifact.name}")
            part.replace(target)
        except Exception:
            part.unlink(missing_ok=True)
            raise

    def provision(self, artifact: ModelArtifact) -> Path:
        model_dir = self.cache_dir / artifact.name
        required = model_dir / artifact.required_file
        if required.is_file() and self._digest(required) == artifact.file_sha256:
            print(f"diarization model cache hit: {artifact.name}")
            return required
        if model_dir.exists():
            shutil.rmtree(model_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        archive = self.cache_dir / (artifact.name + (".tar.bz2" if artifact.archive else ".download"))
        self._download(artifact, archive)
        temporary = Path(tempfile.mkdtemp(prefix=f".{artifact.name}-", dir=self.cache_dir))
        try:
            if artifact.archive:
                self._safe_extract(archive, temporary)
                candidates = list(temporary.rglob(artifact.required_file))
                if len(candidates) != 1:
                    raise DiarizationError(f"missing model file: {artifact.required_file}")
                source_dir = candidates[0].parent
                shutil.move(str(source_dir), str(model_dir))
            else:
                temporary_file = temporary / artifact.required_file
                archive.replace(temporary_file)
                temporary.replace(model_dir)
            if not required.is_file():
                raise DiarizationError(f"missing model file: {artifact.required_file}")
            if self._digest(required) != artifact.file_sha256:
                raise DiarizationError(f"model file checksum mismatch for {artifact.name}")
            return required
        except (tarfile.TarError, OSError) as exc:
            raise DiarizationError(f"could not extract {artifact.name}: {type(exc).__name__}") from exc
        finally:
            archive.unlink(missing_ok=True)
            if temporary.exists():
                shutil.rmtree(temporary)


class DiarizationBackend(Protocol):
    name: str

    def diarize(self, audio: Path, *, num_speakers: int | None) -> list[SpeakerTurn]: ...


class SherpaOnnxDiarizationBackend:
    name = "sherpa-onnx"

    def __init__(
        self,
        manager: DiarizationModelManager | None = None,
        *,
        clustering_threshold: float = 0.5,
        min_duration_on: float = 0.3,
        min_duration_off: float = 0.5,
    ) -> None:
        manager = manager or DiarizationModelManager()
        segmentation = manager.provision(SEGMENTATION_ARTIFACT)
        embedding = manager.provision(EMBEDDING_ARTIFACT)
        try:
            import sherpa_onnx
        except ImportError as exc:
            raise DiarizationError("sherpa-onnx is not installed; install .[diarization]") from exc
        self.sherpa = sherpa_onnx
        self.segmentation = segmentation
        self.embedding = embedding
        self.clustering_threshold = clustering_threshold
        self.min_duration_on = min_duration_on
        self.min_duration_off = min_duration_off
        self.last_num_clusters: int | None = None

    def diarize(self, audio: Path, *, num_speakers: int | None) -> list[SpeakerTurn]:
        try:
            import soundfile as sf

            samples, sample_rate = sf.read(audio, dtype="float32", always_2d=True)
            if sample_rate != 16000 or samples.shape[1] != 1:
                raise DiarizationError("diarization audio must be mono 16 kHz")
            config = self.sherpa.OfflineSpeakerDiarizationConfig(
                segmentation=self.sherpa.OfflineSpeakerSegmentationModelConfig(
                    pyannote=self.sherpa.OfflineSpeakerSegmentationPyannoteModelConfig(
                        model=str(self.segmentation)
                    ),
                    provider="cpu",
                ),
                embedding=self.sherpa.SpeakerEmbeddingExtractorConfig(
                    model=str(self.embedding), provider="cpu"
                ),
                clustering=self.sherpa.FastClusteringConfig(
                    num_clusters=num_speakers if num_speakers is not None else -1,
                    threshold=getattr(self, "clustering_threshold", 0.5),
                ),
                min_duration_on=getattr(self, "min_duration_on", 0.3),
                min_duration_off=getattr(self, "min_duration_off", 0.5),
            )
            self.last_num_clusters = config.clustering.num_clusters
            if num_speakers is not None and self.last_num_clusters != num_speakers:
                raise DiarizationError(
                    "sherpa clustering speaker count was not applied: "
                    f"requested={num_speakers} configured={self.last_num_clusters}"
                )
            if not config.validate():
                raise DiarizationError("invalid sherpa-onnx diarization configuration")
            diarizer = self.sherpa.OfflineSpeakerDiarization(config)
            result = diarizer.process(samples[:, 0]).sort_by_start_time()
            return [
                SpeakerTurn(float(turn.start), float(turn.end), f"speaker_{int(turn.speaker):02d}")
                for turn in result
            ]
        except DiarizationError:
            raise
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
    # Sherpa can emit a short speaker turn nested inside a long turn for another
    # speaker. A word wholly inside both then has equal overlap. Prefer the more
    # temporally specific turn instead of collapsing every tie to SPEAKER_00.
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
                if rows and rows[-1]["speaker"] == speaker and row["start"] - rows[-1]["end"] <= merge_gap:
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


def smooth_speaker_turns(
    rows: list[dict[str, Any]], config: DiarizationConfig
) -> tuple[list[dict[str, Any]], dict[str, int]]:
    """Conservatively remove weak same-speaker sandwich micro-turns."""

    smoothed = [dict(row) for row in rows]
    before = len(smoothed)
    switches_before = _speaker_switches(smoothed)
    merged = preserved = 0
    if config.smoothing_enabled:
        index = 1
        while index < len(smoothed) - 1:
            previous, candidate, following = smoothed[index - 1:index + 2]
            duration = max(0.0, float(candidate["end"]) - float(candidate["start"]))
            word_count = int(candidate.get("aligned_word_count") or len(str(candidate.get("text") or "").split()))
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
            boundary = str(previous.get("text") or "").rstrip().endswith(tuple(".!؟?")) or str(
                candidate.get("text") or ""
            ).rstrip().endswith(tuple(".!؟?"))
            eligible = same_speaker_sandwich and local and micro
            if eligible and weak and (near_zero or not boundary):
                previous["text"] = join_word_tokens([
                    str(previous.get("text") or ""), str(candidate.get("text") or ""),
                    str(following.get("text") or ""),
                ])
                previous["end"] = following["end"]
                previous["aligned_word_count"] = sum(
                    int(row.get("aligned_word_count") or len(str(row.get("text") or "").split()))
                    for row in (previous, candidate, following)
                )
                smoothed[index - 1:index + 2] = [previous]
                merged += 1
                index = max(1, index - 1)
                continue
            if eligible:
                preserved += 1
            index += 1
    return smoothed, {
        "pre_smoothing_segments": before,
        "post_smoothing_segments": len(smoothed),
        "speaker_switches_before": switches_before,
        "speaker_switches_after": _speaker_switches(smoothed),
        "micro_turns_merged": merged,
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


def run_diarization(audio: Path, segments: list[dict[str, Any]], config: DiarizationConfig, *, backend: DiarizationBackend | None = None, output: Path | None = None) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    started = time.monotonic()
    backend = backend or SherpaOnnxDiarizationBackend(
        DiarizationModelManager(config.model_cache_dir),
        clustering_threshold=config.clustering_threshold,
        min_duration_on=config.min_duration_on,
        min_duration_off=config.min_duration_off,
    )
    raw_turns = backend.diarize(audio, num_speakers=config.num_speakers)
    turns = normalize_turns(raw_turns)
    if not turns:
        raise DiarizationError("diarization returned zero speakers")
    aligned, ambiguous = align_segments(segments, turns, merge_gap=config.merge_gap_seconds)
    aligned, smoothing_diagnostics = smooth_speaker_turns(aligned, config)
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
        "models": {
            "segmentation": config.segmentation_model,
            "embedding": config.embedding_model,
        }, "requested_speaker_count": config.num_speakers,
        "raw_turn_count": len(raw_turns),
        "raw_speakers": sorted({turn.speaker for turn in raw_turns}),
        "normalized_turn_count": len(turns),
        "normalized_speakers": sorted(durations),
        "detected_speaker_count": len(durations), "speaker_durations": durations,
        "speaker_turn_count": len(turns), "speaker_turn_counts": dict(turn_counts),
        "aligned_segment_counts": dict(aligned_segment_counts),
        "aligned_word_counts": dict(aligned_word_counts),
        "unassigned_word_count": unassigned_words,
        "ambiguous_word_count": ambiguous,
        "ambiguous_assignments": ambiguous,
        **smoothing_diagnostics,
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
        "config": {
            key: str(value) if isinstance(value, Path) else value
            for key, value in asdict(config).items()
        },
        "turns": [asdict(t) for t in turns],
    }
    if output:
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
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
