"""CLI shim that adds an opt-in pyannote Community-1 diarization path."""

from __future__ import annotations

import json
from dataclasses import replace
from pathlib import Path
from typing import Any

from vid_pipeline import accuracy, reliable_cli
from vid_pipeline import diarization as diarization_module
from vid_pipeline.diarization import DiarizationConfig, run_diarization
from vid_pipeline.pyannote_diarization import (
    PYANNOTE_BACKEND_NAME,
    PYANNOTE_MODEL_ID,
    PyannoteDiarizationBackend,
)
from vid_pipeline.role_mapping import map_roles, map_roles_with_diagnostics

_ORIGINAL_OPTIONAL_ENRICHMENT = accuracy.optional_enrichment


def _pyannote_optional_enrichment(
    audio: Path,
    segments: list[dict[str, Any]],
    config: accuracy.AccuracyConfig,
) -> tuple[list[dict[str, Any]], list[str]]:
    if not config.diarization:
        return _ORIGINAL_OPTIONAL_ENRICHMENT(audio, segments, config)

    # Preserve WhisperX alignment behavior before pyannote diarization.
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
        model_cache_dir=config.diarization_cache_dir,
        role_mode=config.speaker_role_mode,
        role_overrides=config.speaker_role_overrides,
    )

    # run_diarization keeps speaker segmentation and role attribution separate,
    # but historically used its module-local heuristic.  Swap in the conservative
    # mapper only for the pyannote path and restore the legacy mapper afterwards.
    original_mapper = diarization_module.map_roles
    diarization_module.map_roles = map_roles
    try:
        aligned, report = run_diarization(
            audio,
            aligned,
            diarization_config,
            backend=backend,
            output=output,
        )
    finally:
        diarization_module.map_roles = original_mapper

    role_mode = (
        config.speaker_role_mode
        if int(report.get("aligned_effective_speaker_count") or 0) == 2
        else "generic"
    )
    mapping, role_diagnostics = map_roles_with_diagnostics(
        aligned,
        role_mode,
        config.speaker_role_overrides,
        diarization_config.role_threshold,
    )

    report["backend"] = PYANNOTE_BACKEND_NAME
    report["models"] = {"pipeline": PYANNOTE_MODEL_ID}
    report["exclusive_speaker_diarization_used"] = backend.last_used_exclusive
    report["pyannote_audio_version"] = backend.pyannote_audio_version
    report["requested_speaker_count"] = config.num_speakers
    report["role_mapping"] = mapping
    report["role_mapping_mode"] = role_mode
    report["role_mapping_status"] = role_diagnostics["status"]
    report["role_mapping_features"] = role_diagnostics["features"]
    report["role_mapping_confidence"] = role_diagnostics["confidence"]
    report["role_mapping_source"] = role_diagnostics["source"]
    report["role_mapping_diagnostics"] = role_diagnostics
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
