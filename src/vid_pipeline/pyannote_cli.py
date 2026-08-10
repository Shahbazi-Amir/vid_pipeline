"""CLI shim that adds an opt-in pyannote Community-1 diarization path."""

from __future__ import annotations

import json
import sys
from dataclasses import replace
from pathlib import Path
from typing import Any

from vid_pipeline import accuracy, reliable_cli
from vid_pipeline import diarization as diarization_module
from vid_pipeline.collection_output import infer_result_number, materialize_collection_output
from vid_pipeline.diarization import DiarizationConfig, run_diarization
from vid_pipeline.github_client import GitHubState, sha256_file
from vid_pipeline.llm_review import AIReviewError, review_collection_output_if_configured
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

    print("PIPELINE_STAGE stage=pyannote_model_load status=started")
    backend = PyannoteDiarizationBackend()
    print("PIPELINE_STAGE stage=pyannote_model_load status=completed")
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
    # but historically used its module-local heuristic. Swap in the conservative
    # mapper only for the pyannote path and restore the legacy mapper afterwards.
    original_mapper = diarization_module.map_roles
    diarization_module.map_roles = map_roles
    try:
        print("PIPELINE_STAGE stage=diarization_alignment status=started")
        aligned, report = run_diarization(
            audio,
            aligned,
            diarization_config,
            backend=backend,
            output=output,
        )
        print("PIPELINE_STAGE stage=diarization_alignment status=completed")
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


def _consume_collection_options(argv: list[str]) -> tuple[list[str], Path | None, int | None]:
    if len(argv) < 3 or argv[1] != "github-submit-file":
        return argv, None, None

    collection_root: Path | None = None
    result_number: int | None = None
    cleaned = [argv[0], argv[1], argv[2]]
    index = 3
    while index < len(argv):
        item = argv[index]
        if item == "--collection-output-root":
            if index + 1 >= len(argv):
                raise ValueError("--collection-output-root requires a path")
            collection_root = Path(argv[index + 1])
            index += 2
            continue
        if item.startswith("--collection-output-root="):
            collection_root = Path(item.split("=", 1)[1])
            index += 1
            continue
        if item == "--result-number":
            if index + 1 >= len(argv):
                raise ValueError("--result-number requires an integer")
            result_number = int(argv[index + 1])
            index += 2
            continue
        if item.startswith("--result-number="):
            result_number = int(item.split("=", 1)[1])
            index += 1
            continue
        if item == "--delete-result-artifact-after-save":
            cleaned.append("--delete-result-artifact-after-download")
            index += 1
            continue
        cleaned.append(item)
        index += 1

    if collection_root is None:
        return cleaned, None, result_number

    without_output_root: list[str] = []
    index = 0
    while index < len(cleaned):
        item = cleaned[index]
        if item == "--output-root":
            index += 2
            continue
        if item.startswith("--output-root="):
            index += 1
            continue
        without_output_root.append(item)
        index += 1
    cleaned = without_output_root

    if "--wait" not in cleaned:
        cleaned.append("--wait")
    if "--download" not in cleaned:
        cleaned.append("--download")
    cleaned.extend(["--output-root", ".vid_pipeline/github-results"])
    return cleaned, collection_root, result_number


def _materialize_collection_result(
    source: Path,
    collection_root: Path,
    result_number: int | None,
) -> Path:
    source = source.resolve()
    state = GitHubState()
    request = state.find_digest(sha256_file(source), source.stat().st_size)
    if request is None or not request.output_path:
        raise ValueError("completed GitHub result state was not found")

    target = collection_root.resolve()
    downloaded = Path(request.output_path).resolve()
    if downloaded != target:
        target = materialize_collection_output(
            downloaded,
            collection_root,
            source,
            result_number=result_number,
        )
    request.output_path = str(target)
    state.save(request)
    return target


def main() -> int:
    accuracy.optional_enrichment = _pyannote_optional_enrichment
    original_argv = sys.argv[:]
    try:
        prepared, collection_root, result_number = _consume_collection_options(original_argv)
        sys.argv = prepared
        result = reliable_cli.main()
        if result == 0 and collection_root is not None:
            source = Path(original_argv[2])
            target = _materialize_collection_result(
                source,
                collection_root,
                result_number,
            )
            number = infer_result_number(source, result_number)
            review = review_collection_output_if_configured(target, number)
            print(
                json.dumps(
                    {
                        "collection_output": str(target),
                        "review": review,
                    },
                    ensure_ascii=False,
                )
            )
        return result
    except (AIReviewError, OSError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    finally:
        sys.argv = original_argv


if __name__ == "__main__":
    raise SystemExit(main())
