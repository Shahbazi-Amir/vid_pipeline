#!/usr/bin/env python3
"""Run sherpa diarization repeatedly on one immutable WAV and compare timelines."""

from __future__ import annotations

import argparse
import json
import platform
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path

from vid_pipeline.diarization import (
    EMBEDDING_ARTIFACT,
    SEGMENTATION_ARTIFACT,
    DiarizationConfig,
    DiarizationModelManager,
    SherpaOnnxDiarizationBackend,
    _audio_manifest,
    _file_manifest,
    _turn_summary,
    compare_diarization_runs,
    select_diarization_consensus,
)


def package_version(name: str) -> str:
    try:
        return version(name)
    except PackageNotFoundError:
        return "not-installed"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("audio", type=Path)
    parser.add_argument("--attempts", type=int, default=3)
    parser.add_argument("--num-speakers", type=int, default=2)
    parser.add_argument("--num-threads", type=int, default=1)
    parser.add_argument("--cache-dir", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    config = DiarizationConfig(
        num_speakers=args.num_speakers,
        num_threads=args.num_threads,
        model_cache_dir=args.cache_dir,
    )
    manager = DiarizationModelManager(args.cache_dir)
    backend = SherpaOnnxDiarizationBackend(
        manager,
        clustering_threshold=config.clustering_threshold,
        min_duration_on=config.min_duration_on,
        min_duration_off=config.min_duration_off,
        num_threads=config.num_threads,
    )
    attempts = []
    for index in range(args.attempts):
        turns = backend.diarize(args.audio, num_speakers=args.num_speakers)
        attempts.append(turns)
        print(json.dumps(_turn_summary(turns, index + 1), sort_keys=True))
    selected, summary = select_diarization_consensus(attempts, config)
    comparisons = []
    for left in range(len(attempts)):
        for right in range(left + 1, len(attempts)):
            comparisons.append({
                "left": left + 1,
                "right": right + 1,
                **compare_diarization_runs(attempts[left], attempts[right]),
            })
    report = {
        "python_version": platform.python_version(),
        "sherpa_onnx_version": package_version("sherpa-onnx"),
        "onnxruntime_version": package_version("onnxruntime"),
        "audio": _audio_manifest(args.audio),
        "models": {
            "segmentation": _file_manifest(
                backend.segmentation, expected_sha256=SEGMENTATION_ARTIFACT.file_sha256
            ),
            "embedding": _file_manifest(
                backend.embedding, expected_sha256=EMBEDDING_ARTIFACT.file_sha256
            ),
        },
        "config": backend.last_config,
        "attempts": [_turn_summary(turns, index + 1) for index, turns in enumerate(attempts)],
        "comparisons": comparisons,
        "summary": summary,
        "selected_attempt": selected + 1,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
