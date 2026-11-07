#!/usr/bin/env python3
"""Second-pass quality-reference ASR for audio 01; never modifies the first-pass output.

The alternate transcript uses the same pinned model with different decoding settings.\nIt is *not* an independent-model or verified transcription and may contain errors.
Original immutable GitHub release asset and its SHA-256 are verified before use.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
from transcribe_four_release import TAG, download, release_assets

NUMBER = "01"
MODEL = "large-v3-turbo"
PROMPT = (
    "کلاس فیزیولوژی سلول. غشای سلولی، سیتوپلاسم، هسته، میتوکندری، "
    "شبکه آندوپلاسمی، ریبوزوم، لیزوزوم، اندامک‌ها، DNA، RNA، کروموزوم، "
    "هیستون، فسفولیپید، کلسترول، پروتئین، ATP، انتشار و انتقال."
)
HOTWORDS = (
    "فیزیولوژی، غشای سلولی، سیتوپلاسم، شبکه آندوپلاسمی، "
    "میتوکندری، فسفولیپید، پروتئین، کروموزوم، نوکلئوزوم، هیستون"
)


def main() -> None:
    output = Path("quality-audio-results") / NUMBER
    output.mkdir(parents=True, exist_ok=True)
    try:
        release, assets = release_assets()
        asset = assets[NUMBER]
        media = Path("reference-audio" + Path(asset["name"]).suffix.lower())
        digest = download(asset, media)
        (output / "source.json").write_text(
            json.dumps({
                "release_tag": TAG,
                "release_url": release.get("html_url"),
                "asset_id": asset["id"],
                "asset_name": asset["name"],
                "sha256": digest,
                "model": MODEL,
                "language": "fa",
                "beam_size": 7,
                "initial_prompt": PROMPT,
                "hotwords": HOTWORDS,
                "purpose": "second_decoding_pass_for_textual_crosscheck",\n                "same_model_as_first_pass": True,
                "audio_review": "not_performed",
                "original_outputs_modified": False,
            }, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
        cmd = [
            sys.executable, "-m", "vid_pipeline.cli", "run-file", str(media),
            "--name", "quality-persian-audio-01", "--output-root", "quality-audio-work",
            "--profile", "accurate", "--model", MODEL, "--language", "fa",
            "--device", "cpu", "--compute-type", "int8", "--audio-profile", "safe",
            "--beam-size", "7", "--initial-prompt", PROMPT,
            "--hotwords", HOTWORDS,
            "--no-editorial",
        ]
        with (output / "worker.log").open("w", encoding="utf-8") as log:
            result = subprocess.run(cmd, stdout=log, stderr=subprocess.STDOUT, check=False)
        if result.returncode:
            raise RuntimeError("Independent ASR failed with return code " + str(result.returncode))
        required = (
            ("*/final/transcript.final.md", "transcript.alt.md"),
            ("*/final/transcript.final.txt", "transcript.alt.txt"),
            ("*/raw/transcript.raw.md", "transcript.alt.timestamped.md"),
            ("*/raw/transcript.raw.json", "transcript.alt.raw.json"),
        )
        for pattern, dest in required:
            matches = list(Path("quality-audio-work").glob(pattern))
            if len(matches) != 1 or matches[0].stat().st_size == 0:
                raise RuntimeError("Quality reference is missing or empty: " + pattern)
            shutil.copyfile(matches[0], output / dest)
        data = json.loads((output / "transcript.alt.raw.json").read_text(encoding="utf-8"))
        if not data.get("segments"):
            raise RuntimeError("Quality reference has no speech segments")
        (output / "status.json").write_text(
            json.dumps({
                "state": "alternate_machine_transcription_complete",
                "segment_count": len(data["segments"]),
                "review": "comparison_pending",
                "human_audio_verification": False,
            }, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
        print("Independent ASR complete:", len(data["segments"]), "segments")
    except Exception as exc:
        (output / "status.json").write_text(
            json.dumps({"state": "failed", "error": str(exc)}, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8"
        )
        raise


if __name__ == "__main__":
    main()
