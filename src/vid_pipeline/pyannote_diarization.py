"""pyannote.audio Community-1 speaker diarization backend."""

from __future__ import annotations

import os
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path
from typing import Any, Callable

from vid_pipeline.diarization import DiarizationError, SpeakerTurn

PYANNOTE_MODEL_ID = "pyannote/speaker-diarization-community-1"
PYANNOTE_BACKEND_NAME = "pyannote-community-1"


def _package_version(name: str) -> str:
    try:
        return version(name)
    except PackageNotFoundError:
        return "not-installed"


def annotation_to_speaker_turns(annotation: Any) -> list[SpeakerTurn]:
    """Convert a pyannote Annotation-like object into project SpeakerTurn rows."""
    if annotation is None:
        raise DiarizationError("pyannote diarization output is missing")

    turns: list[SpeakerTurn] = []
    if hasattr(annotation, "itertracks"):
        for item in annotation.itertracks(yield_label=True):
            if len(item) != 3:
                raise DiarizationError("unexpected pyannote diarization track format")
            segment, _track, speaker = item
            turns.append(
                SpeakerTurn(float(segment.start), float(segment.end), str(speaker))
            )
    else:
        try:
            iterator = iter(annotation)
        except TypeError:
            raise DiarizationError("unsupported pyannote diarization output") from None
        for item in iterator:
            if not isinstance(item, tuple) or len(item) != 2:
                raise DiarizationError("unexpected pyannote diarization item format")
            segment, speaker = item
            turns.append(
                SpeakerTurn(float(segment.start), float(segment.end), str(speaker))
            )

    return sorted(turns, key=lambda turn: (turn.start, turn.end, turn.speaker))


class PyannoteDiarizationBackend:
    """Local Community-1 backend using a dedicated, non-exported HF token."""

    name = PYANNOTE_BACKEND_NAME
    model_id = PYANNOTE_MODEL_ID

    def __init__(
        self,
        *,
        token: str | None = None,
        pipeline_loader: Callable[..., Any] | None = None,
    ) -> None:
        resolved_token = (
            token
            or os.getenv("VID_PIPELINE_PYANNOTE_TOKEN", "")
            or os.getenv("HF_TOKEN", "")
        ).strip()
        if not resolved_token:
            raise DiarizationError(
                "HF_TOKEN is required for pyannote Community-1 model download"
            )

        if pipeline_loader is None:
            try:
                from pyannote.audio import Pipeline
            except ImportError as exc:
                raise DiarizationError(
                    "pyannote.audio is not installed; install .[diarization-pyannote]"
                ) from exc
            pipeline_loader = Pipeline.from_pretrained

        try:
            pipeline = pipeline_loader(self.model_id, token=resolved_token)
        except Exception as exc:
            # Never include upstream exception text because request metadata can
            # accidentally echo credentials into CI logs.
            raise DiarizationError(
                f"pyannote model load failed: {type(exc).__name__}"
            ) from None

        if pipeline is None:
            raise DiarizationError("pyannote model load failed: empty pipeline")

        self.pipeline = pipeline
        self.pyannote_audio_version = _package_version("pyannote.audio")
        self.last_used_exclusive = False
        self.last_requested_speakers: int | None = None

    def diarize(
        self, audio: Path, *, num_speakers: int | None
    ) -> list[SpeakerTurn]:
        kwargs: dict[str, Any] = {}
        if num_speakers is not None:
            kwargs["num_speakers"] = num_speakers

        try:
            output = self.pipeline(str(audio), **kwargs)
        except Exception as exc:
            raise DiarizationError(
                f"pyannote diarization inference failed: {type(exc).__name__}"
            ) from None

        self.last_requested_speakers = num_speakers

        exclusive = getattr(output, "exclusive_speaker_diarization", None)
        regular = getattr(output, "speaker_diarization", None)

        if exclusive is not None:
            annotation = exclusive
            self.last_used_exclusive = True
        elif regular is not None:
            annotation = regular
            self.last_used_exclusive = False
        elif hasattr(output, "itertracks"):
            annotation = output
            self.last_used_exclusive = False
        else:
            raise DiarizationError("pyannote diarization returned no usable timeline")

        turns = annotation_to_speaker_turns(annotation)
        if not turns:
            raise DiarizationError("pyannote diarization returned zero speaker turns")
        return turns
