#!/usr/bin/env python3
"""Process one cataloged Asre Shirin season-two episode through review packaging."""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
from pathlib import Path

from vid_pipeline.audio import require_tool
from vid_pipeline.models import EpisodeSpec
from vid_pipeline.pipeline import EpisodePipeline
from vid_pipeline.transcribe import TranscriptionConfig


def clean_title(value: str) -> str:
    value = value.replace("| آکادمی هوش مالی", "").replace("- آکادمی هوش مالی", "")
    return " ".join(value.split()).strip()


def load_entry(path: Path, season_episode: int) -> dict[str, object]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if data.get("status") != "ready":
        raise RuntimeError(f"Catalog is not ready: {data.get('status')}")
    matches = [
        item
        for item in data.get("season_two", [])
        if int(item.get("season_episode") or 0) == season_episode
    ]
    if len(matches) != 1:
        raise RuntimeError(f"Expected one catalog entry for episode {season_episode}, got {len(matches)}")
    entry = matches[0]
    if not entry.get("speaker_verified") or not entry.get("program_verified"):
        raise RuntimeError("Catalog entry lacks source/speaker verification")
    return entry


def make_review_audio(source: Path, destination: Path) -> Path:
    ffmpeg = require_tool("ffmpeg")
    destination.parent.mkdir(parents=True, exist_ok=True)
    command = [
        ffmpeg,
        "-hide_banner",
        "-loglevel",
        "error",
        "-y",
        "-i",
        str(source),
        "-vn",
        "-ac",
        "1",
        "-ar",
        "16000",
        "-c:a",
        "libmp3lame",
        "-b:a",
        "40k",
        str(destination),
    ]
    result = subprocess.run(command, capture_output=True, text=True, check=False)
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or "Could not create review audio")
    return destination


def copy_review_bundle(pipeline: EpisodePipeline, spec_path: Path, destination: Path) -> None:
    destination.mkdir(parents=True, exist_ok=True)
    copies = {
        spec_path: destination / "episode.json",
        pipeline.paths.source_metadata: destination / "source.json",
        pipeline.paths.video_metadata: destination / "video-info.json",
        pipeline.paths.state: destination / "state.json",
        pipeline.paths.raw_json: destination / f"episode-{pipeline.spec.season_episode:02d}.raw.json",
        pipeline.paths.raw_markdown: destination / f"episode-{pipeline.spec.season_episode:02d}.raw.md",
        pipeline.paths.review_markdown: destination / f"episode-{pipeline.spec.season_episode:02d}.review.md",
    }
    for source, target in copies.items():
        if source.exists() and source.resolve() != target.resolve():
            shutil.copy2(source, target)
    make_review_audio(
        pipeline.paths.audio,
        destination / f"episode-{pipeline.spec.season_episode:02d}.review.mp3",
    )
    summary = {
        "program": pipeline.spec.program,
        "season": pipeline.spec.season,
        "season_episode": pipeline.spec.season_episode,
        "overall_episode": pipeline.spec.overall_episode,
        "title": pipeline.spec.title,
        "source_url": pipeline.spec.source_url,
        "video_url": pipeline.spec.video_url,
        "status": "needs_review",
        "reviewed": False,
        "note": "Automatic transcription completed; genuine audio review is still required.",
    }
    (destination / "result.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--catalog", type=Path, required=True)
    parser.add_argument("--season-episode", type=int, required=True)
    parser.add_argument("--work-root", type=Path, default=Path("work"))
    parser.add_argument("--output-root", type=Path, default=Path("stage/season2"))
    parser.add_argument("--model", default="small")
    parser.add_argument("--device", default="cpu")
    parser.add_argument("--compute-type", default="int8")
    args = parser.parse_args()

    entry = load_entry(args.catalog, args.season_episode)
    overall_episode = int(entry["overall_episode"])
    output_dir = args.output_root / f"episode-{args.season_episode:02d}"
    output_dir.mkdir(parents=True, exist_ok=True)
    spec_path = output_dir / "episode.json"
    spec = EpisodeSpec(
        program="عصر شیرین",
        collection="asre-shirin-season-2",
        season="فصل دوم",
        season_episode=args.season_episode,
        overall_episode=overall_episode,
        speaker="دکتر کمیل رودی",
        title=clean_title(str(entry.get("title") or "")),
        source_url=str(entry["source_url"]),
        video_url=str(entry["video_url"]),
        additional_speakers=["مجری برنامه", "شرکت‌کنندگان کارگاه"],
        search_site="https://www.fintelligence.ir/",
        source_verified=True,
        speaker_verified=True,
    )
    spec.save(spec_path)
    pipeline = EpisodePipeline(spec, args.work_root)
    config = TranscriptionConfig(
        model=args.model,
        device=args.device,
        compute_type=args.compute_type,
        beam_size=5,
    )
    try:
        results = pipeline.run_automatic(config=config)
        spec.save(spec_path)
        copy_review_bundle(pipeline, spec_path, output_dir)
        print(json.dumps(results, ensure_ascii=False, indent=2))
        return 0
    except Exception as exc:
        error = {
            "season_episode": args.season_episode,
            "overall_episode": overall_episode,
            "status": "failed",
            "error_type": type(exc).__name__,
            "error": str(exc),
        }
        (output_dir / "result.json").write_text(
            json.dumps(error, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        print(json.dumps(error, ensure_ascii=False, indent=2), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
