"""CLI shim that adds an opt-in pyannote Community-1 diarization path."""

from __future__ import annotations

import json
import os
from dataclasses import replace
from pathlib import Path
from typing import Any

from vid_pipeline import accuracy
from vid_pipeline.diarization import DiarizationConfig, run_diarization
from vid_pipeline.pyannote_diarization import (
    PYANNOTE_BACKEND_NAME,
    PYANNOTE_MODEL_ID,
    PyannoteDiarizationBackend,
)
from vid_pipeline import reliable_cli

_ORIGINAL_OPTIONAL_ENRICHMENT = accuracy.optional_enrichment


def _pyannote_optional_enrichment(
    audio: Path,
    segments: list[dict[str, Any]],
    config: accuracy.AccuracyConfig,
) -> tuple[list[dict[str, Any]], list[str]]:
    backend_name = os.getenv("VID_PIPELINE_DIARIZATION_BACKEND", "sherpa-onnx").strip()
    if backend_name != PYANNOTE_BACKEND_NAME or not config.diarization:
        return _ORIGINAL_OPTIONAL_ENRICHMENT(audio, segments, config)

    # Preserve WhisperX alignment behavior, but suppress the legacy Sherpa call.
    aligned, warnings = _ORIGINAL_OPTIONAL_ENRICHMENT(
        audio,
        segments,
        replace(config, diarization=False),
    )

    backend = PyannoteDiarizationBackend()
    output = audio.parents[1] / "diarization" / "diarization.json"
    diarization_config = DiarizationConfig(
        enabled=True,
        required=config.diarization_required,
        num_speakers=config.num_speakers,
        backend=PYANNOTE_BACKEND_NAME,
        segmentation_model=PYANNOTE_MODEL_ID,
        embedding_model="",
        model_cache_dir=config.diarization_cache_dir,
        role_mode=config.speaker_role_mode,
        role_overrides=config.speaker_role_overrides,
    )
    aligned, report = run_diarization(
        audio,
        aligned,
        diarization_config,
        backend=backend,
        output=output,
    )
    report["backend"] = PYANNOTE_BACKEND_NAME
    report["models"] = {"pipeline": PYANNOTE_MODEL_ID}
    report["exclusive_speaker_diarization_used"] = backend.last_used_exclusive
    report["pyannote_audio_version"] = backend.pyannote_audio_version
    report["requested_speaker_count"] = config.num_speakers
    output.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return aligned, warnings


def main() -> int:
    accuracy.optional_enrichment = _pyannote_optional_enrichment
    return reliable_cli.main()


if __name__ == "__main__":
    raise SystemExit(main())
