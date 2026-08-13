"""pyannote.audio Community-1 speaker diarization backend."""

from __future__ import annotations

import os
import time
from collections.abc import Callable
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path
from typing import Any

from vid_pipeline.diarization import DiarizationError, SpeakerTurn

PYANNOTE_MODEL_ID = "pyannote/speaker-diarization-community-1"
PYANNOTE_BACKEND_NAME = "pyannote-community-1"


def load_waveform(audio: Path) -> dict[str, Any]:
    """Load verified PCM audio without pyannote's optional TorchCodec decoder.

    The shared pipeline always hands this backend the normalized local WAV. Passing an
    in-memory waveform keeps that file as the single compute input and avoids
    TorchCodec selecting a CUDA-linked decoder wheel on CPU-only runners.
    """

    if not audio.is_file() or audio.stat().st_size <= 0:
        raise DiarizationError("pyannote waveform input is missing or empty")
    try:
        import soundfile as sf
        import torch

        frames, sample_rate = sf.read(
            str(audio), dtype="float32", always_2d=True
        )
        if frames.shape[0] <= 0 or frames.shape[1] <= 0 or int(sample_rate) <= 0:
            raise ValueError("empty decoded waveform")
        waveform = torch.from_numpy(frames.T.copy())
    except DiarizationError:
        raise
    except Exception as exc:
        raise DiarizationError(
            f"pyannote waveform load failed: {type(exc).__name__}"
        ) from None
    return {"waveform": waveform, "sample_rate": int(sample_rate)}


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
        waveform_loader: Callable[[Path], dict[str, Any]] | None = None,
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

        # pyannote forwards the explicit token to its top-level pipeline loader,
        # but nested Hugging Face Hub downloads can consult HF_TOKEN directly.
        # Mirror the dedicated pipeline token only when HF_TOKEN is absent/empty
        # so all dependent model fetches are authenticated without printing it.
        if not os.getenv("HF_TOKEN", "").strip():
            os.environ["HF_TOKEN"] = resolved_token

        if pipeline_loader is None:
            try:
                from pyannote.audio import Pipeline
            except ImportError as exc:
                raise DiarizationError(
                    "pyannote.audio is not installed; install .[diarization-pyannote]"
                ) from exc
            pipeline_loader = Pipeline.from_pretrained

        model_load_started = time.monotonic()
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
        self.waveform_loader = waveform_loader or load_waveform
        self._loaded_audio_path: Path | None = None
        self._waveform_input: dict[str, Any] | None = None
        self.model_load_seconds = time.monotonic() - model_load_started
        self.audio_load_seconds = 0.0
        self.inference_seconds = 0.0
        self.pyannote_audio_version = _package_version("pyannote.audio")
        self.last_used_exclusive = False
        self.last_requested_speakers: int | None = None

    def diarize(
        self, audio: Path, *, num_speakers: int | None
    ) -> list[SpeakerTurn]:
        kwargs: dict[str, Any] = {}
        if num_speakers is not None:
            kwargs["num_speakers"] = num_speakers

        resolved_audio = audio.resolve()
        if self._loaded_audio_path != resolved_audio or self._waveform_input is None:
            audio_load_started = time.monotonic()
            try:
                self._waveform_input = self.waveform_loader(audio)
            except DiarizationError:
                raise
            except Exception as exc:
                raise DiarizationError(
                    f"pyannote waveform load failed: {type(exc).__name__}"
                ) from None
            self.audio_load_seconds += time.monotonic() - audio_load_started
            self._loaded_audio_path = resolved_audio

        inference_started = time.monotonic()
        try:
            output = self.pipeline(self._waveform_input, **kwargs)
        except Exception as exc:
            raise DiarizationError(
                f"pyannote diarization inference failed: {type(exc).__name__}"
            ) from None
        self.inference_seconds += time.monotonic() - inference_started

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
