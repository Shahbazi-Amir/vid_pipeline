#!/usr/bin/env python3
"""Run pyannote diarization repeatedly on one immutable WAV and compare timelines."""

from __future__ import annotations

import argparse
import json
import platform
from pathlib import Path

from vid_pipeline.diarization import (
    DiarizationConfig,
    _audio_manifest,
    _turn_summary,
    compare_diarization_runs,
    select_diarization_consensus,
)
from vid_pipeline.pyannote_diarization import (
    PYANNOTE_MODEL_ID,
    PyannoteDiarizationBackend,
)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("audio", type=Path)
    parser.add_argument("--attempts", type=int, default=3)
    parser.add_argument("--num-speakers", type=int, default=2)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    config = DiarizationConfig(num_speakers=args.num_speakers)
    backend = PyannoteDiarizationBackend()
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
        "backend": backend.name,
        "model_id": PYANNOTE_MODEL_ID,
        "pyannote_audio_version": backend.pyannote_audio_version,
        "audio": _audio_manifest(args.audio),
        "attempts": [
            _turn_summary(turns, index + 1)
            for index, turns in enumerate(attempts)
        ],
        "comparisons": comparisons,
        "summary": summary,
        "selected_attempt": selected + 1,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(report, indent=2) + "\n", encoding="utf-8"
    )


if __name__ == "__main__":
    main()
