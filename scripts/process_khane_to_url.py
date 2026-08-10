from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from dataclasses import replace
from pathlib import Path

import process_asre_shirin_url as shared
from vid_pipeline import cli as base_cli
from vid_pipeline import pyannote_cli, reliable_cli
from vid_pipeline.aparat import ensure_verified_aparat_media, resolve_aparat_media
from vid_pipeline.asre_shirin import AsreShirinCheckpoints, collect_timing, total_worker_seconds
from vid_pipeline.standalone import LocalMediaPipeline

PROGRAM = "خانه تو"
HOST = "فرهاد جم"
GUEST = "دکتر کمیل رودی"


def run_pipeline(media_path: Path, source_url: str, episode: int, title: str, output_root: Path) -> int:
    original_accuracy_config = reliable_cli._accuracy_config

    def automatic_speaker_accuracy_config(args):
        config = original_accuracy_config(args)
        return replace(config, num_speakers=None, speaker_role_mode="generic")

    reliable_cli._accuracy_config = automatic_speaker_accuracy_config
    original_argv = sys.argv[:]
    try:
        sys.argv = [
            "vid-pipeline", "run-file", str(media_path),
            "--source-url", source_url,
            "--output-root", str(output_root),
            "--name", f"khane-to-{episode}",
            "--title", title or f"خانه تو | قسمت {episode}",
            "--program", PROGRAM,
            "--guest", GUEST,
            "--speaker", HOST,
            "--speaker", GUEST,
            "--profile", "balanced",
            "--model", "large-v3-turbo",
            "--language", "fa",
            "--device", "cpu",
            "--compute-type", "int8",
            "--no-editorial",
            "--diarize",
            "--diarization-required",
            "--speaker-role-mode", "generic",
            "--resume",
        ]
        return pyannote_cli.main()
    finally:
        reliable_cli._accuracy_config = original_accuracy_config
        sys.argv = original_argv


def run_primary_asr(media_path: Path, source_url: str, episode: int, title: str, output_root: Path) -> int:
    original_argv = sys.argv[:]
    try:
        sys.argv = [
            "vid-pipeline", "run-file", str(media_path),
            "--source-url", source_url,
            "--output-root", str(output_root),
            "--name", f"khane-to-{episode}",
            "--title", title or f"خانه تو | قسمت {episode}",
            "--profile", "balanced",
            "--model", "large-v3-turbo",
            "--language", "fa",
            "--device", "cpu",
            "--compute-type", "int8",
            "--no-editorial",
            "--no-diarize",
            "--resume",
        ]
        return base_cli.main()
    finally:
        sys.argv = original_argv


def pipeline_for(media_path: Path, pipeline_root: Path, episode: int) -> LocalMediaPipeline:
    return LocalMediaPipeline(media_path, pipeline_root, f"khane-to-{episode}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", required=True)
    parser.add_argument("--episode", required=True, type=int)
    parser.add_argument("--expected-uid", default="")
    parser.add_argument("--title", default="")
    parser.add_argument("--collection-root", type=Path, required=True)
    parser.add_argument("--work-root", type=Path, default=Path("worker-output"))
    parser.add_argument("--resolver-only", action="store_true")
    parser.add_argument("--ingest-only", action="store_true")
    parser.add_argument("--asr-only", action="store_true")
    args = parser.parse_args()

    if not 1 <= args.episode <= 13:
        raise SystemExit("episode must be 1..13")

    if args.resolver_only:
        resolved = resolve_aparat_media(args.url, expected_uid=args.expected_uid or None)
        print(json.dumps({
            "episode": args.episode,
            "uid": resolved.uid,
            "resolver_type": resolved.resolver_type,
            "media_profile": resolved.profile,
            "duration_seconds": resolved.duration_seconds,
            "status": "resolved",
        }, ensure_ascii=False))
        return

    worker_started = time.monotonic()
    args.work_root.mkdir(parents=True, exist_ok=True)
    args.collection_root.mkdir(parents=True, exist_ok=True)
    ledger = AsreShirinCheckpoints(args.work_root / "khane-to-checkpoints.json")
    ingest_root = args.work_root / "ingest" / f"episode-{args.episode}"
    media_path = ingest_root / "media.mp4"
    media_metadata_path = ingest_root / "media.json"

    ingest = ensure_verified_aparat_media(
        args.url,
        media_path,
        media_metadata_path,
        expected_uid=args.expected_uid or None,
    )
    ledger.mark_complete(
        "media_downloaded_verified",
        [media_path, media_metadata_path],
        shared._safe_ingest_metadata(ingest),
    )
    if args.ingest_only:
        print(json.dumps({"episode": args.episode, "status": "ingest_complete"}))
        return

    pipeline_root = args.work_root / "pipeline"
    pipeline = pipeline_for(media_path, pipeline_root, args.episode)

    if args.asr_only:
        status = run_primary_asr(media_path, args.url, args.episode, args.title, pipeline_root)
        pipeline = pipeline_for(media_path, pipeline_root, args.episode)
        shared._sync_compute_checkpoints(ledger, pipeline)
        if status != 0 or not ledger.is_complete("raw_asr_complete"):
            ledger.mark_failed("raw_asr_complete", f"pipeline_return_code_{status}")
            raise SystemExit(status or 1)
        print(json.dumps({"episode": args.episode, "status": "asr_complete"}))
        return

    role_outputs = [
        args.collection_root / "md" / f"{args.episode}.md",
        args.collection_root / "timestamped" / f"{args.episode}.md",
        args.collection_root / "txt" / f"{args.episode}.txt",
        args.collection_root / "roles" / f"{args.episode}.json",
    ]
    artifact_prepare_seconds = 0.0
    role_mapping_seconds = 0.0

    if not ledger.is_complete("diarization_complete"):
        status = run_pipeline(media_path, args.url, args.episode, args.title, pipeline_root)
        pipeline = pipeline_for(media_path, pipeline_root, args.episode)
        shared._sync_compute_checkpoints(ledger, pipeline)
        if status != 0 or not ledger.is_complete("diarization_complete"):
            ledger.mark_failed("diarization_complete", f"pipeline_return_code_{status}")
            raise SystemExit(status or 1)

    artifact_prepare_started = time.monotonic()
    shared.copy_delivery(pipeline.paths.job_root, args.collection_root, args.episode)
    role_started = time.monotonic()
    subprocess.run([
        sys.executable,
        "scripts/label_khane_to_roles.py",
        str(args.collection_root),
        str(args.episode),
    ], check=True)
    role_mapping_seconds = time.monotonic() - role_started
    artifact_prepare_seconds = time.monotonic() - artifact_prepare_started
    ledger.mark_complete(
        "role_mapping_complete",
        role_outputs,
        {"role_mapping_seconds": round(role_mapping_seconds, 6)},
    )

    timing = collect_timing(
        pipeline.paths.job_root,
        ingest,
        role_mapping_seconds=role_mapping_seconds,
        artifact_prepare_seconds=artifact_prepare_seconds,
        total_worker_seconds=total_worker_seconds(worker_started),
    )
    timings = args.collection_root / "timings"
    timings.mkdir(parents=True, exist_ok=True)
    timing_path = timings / f"{args.episode}.json"
    timing_path.write_text(json.dumps(timing, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    sources = args.collection_root / "sources"
    sources.mkdir(parents=True, exist_ok=True)
    source_path = sources / f"{args.episode}.json"
    source_payload = {
        "episode": args.episode,
        "program": PROGRAM,
        "host": HOST,
        "guest": GUEST,
        "url": args.url,
        "title": args.title or f"خانه تو | قسمت {args.episode}",
        "platform": "Aparat",
        "media": shared._safe_ingest_metadata(ingest),
        "compute_handoff": "run-file",
        "asr_model": "large-v3-turbo",
        "profile": "balanced",
        "device": "cpu",
        "compute_type": "int8",
        "diarization": "pyannote-community-1-auto-speaker-count",
        "external_ai_review": False,
    }
    source_path.write_text(json.dumps(source_payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    final_outputs = [*role_outputs, source_path, timing_path]
    ledger.mark_complete(
        "delivery_complete",
        final_outputs,
        {"total_worker_seconds": timing["total_worker_seconds"]},
    )
    print(json.dumps({
        "episode": args.episode,
        "status": "complete",
        "program": PROGRAM,
        "host": HOST,
        "guest": GUEST,
        "timing": timing,
    }, ensure_ascii=False))


if __name__ == "__main__":
    os.environ.setdefault("AI_REVIEW_ENABLED", "false")
    main()
