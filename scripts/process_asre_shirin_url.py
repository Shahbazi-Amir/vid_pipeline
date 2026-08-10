from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import time
from dataclasses import replace
from pathlib import Path

from vid_pipeline import pyannote_cli, reliable_cli
from vid_pipeline.aparat import ensure_verified_aparat_media, resolve_aparat_media
from vid_pipeline.asre_shirin import AsreShirinCheckpoints, collect_timing
from vid_pipeline.standalone import LocalMediaPipeline


def run_pipeline(
    media_path: Path,
    source_url: str,
    episode: int,
    title: str,
    output_root: Path,
) -> int:
    """Use the canonical local-media compute path; Aparat is never inspected here."""

    original_accuracy_config = reliable_cli._accuracy_config

    def automatic_speaker_accuracy_config(args):
        config = original_accuracy_config(args)
        return replace(config, num_speakers=None, speaker_role_mode="generic")

    reliable_cli._accuracy_config = automatic_speaker_accuracy_config
    original_argv = sys.argv[:]
    try:
        sys.argv = [
            "vid-pipeline",
            "run-file",
            str(media_path),
            "--source-url",
            source_url,
            "--output-root",
            str(output_root),
            "--name",
            f"asre-shirin-{episode}",
            "--title",
            title or f"سواد مالی در عصر شیرین | قسمت {episode}",
            "--program",
            "سواد مالی در عصر شیرین",
            "--guest",
            "دکتر کمیل رودی",
            "--speaker",
            "خانم متولیان",
            "--speaker",
            "دکتر کمیل رودی",
            "--profile",
            "balanced",
            "--model",
            "large-v3-turbo",
            "--language",
            "fa",
            "--device",
            "cpu",
            "--compute-type",
            "int8",
            "--no-editorial",
            "--diarize",
            "--diarization-required",
            "--speaker-role-mode",
            "generic",
            "--resume",
        ]
        return pyannote_cli.main()
    finally:
        reliable_cli._accuracy_config = original_accuracy_config
        sys.argv = original_argv


def _pipeline(media_path: Path, pipeline_root: Path, episode: int) -> LocalMediaPipeline:
    return LocalMediaPipeline(media_path, pipeline_root, f"asre-shirin-{episode}")


def _sync_compute_checkpoints(
    ledger: AsreShirinCheckpoints,
    pipeline: LocalMediaPipeline,
) -> None:
    state = pipeline.state
    if state.is_complete("audio"):
        ledger.mark_complete(
            "audio_normalized",
            [pipeline.paths.audio],
            (state.stage("audio").get("details") or {}),
        )
    if state.is_complete("transcribe"):
        ledger.mark_complete(
            "raw_asr_complete",
            [pipeline.paths.raw_json, pipeline.paths.raw_markdown],
            (state.stage("transcribe").get("details") or {}),
        )
    diarization = pipeline.paths.job_root / "diarization" / "diarization.json"
    consensus = pipeline.paths.job_root / "accuracy" / "transcript.consensus.json"
    if state.is_complete("accuracy") and diarization.is_file() and consensus.is_file():
        report = json.loads(diarization.read_text(encoding="utf-8"))
        if report.get("status") != "completed":
            raise RuntimeError("Diarization report did not pass its required quality gate")
        ledger.mark_complete(
            "diarization_complete",
            [diarization, consensus],
            {
                "raw_speaker_count": report.get("raw_speaker_count")
                or len(report.get("raw_speakers") or []),
                "aligned_effective_speaker_count": report.get(
                    "aligned_effective_speaker_count"
                ),
            },
        )


def copy_delivery(job_root: Path, collection_root: Path, episode: int) -> Path:
    delivery = job_root / "delivery"
    if not delivery.is_dir():
        raise RuntimeError(f"Delivery directory is missing: {delivery}")
    targets = {
        "transcript.md": collection_root / "md" / f"{episode}.md",
        "transcript.timestamped.md": collection_root / "timestamped" / f"{episode}.md",
        "transcript.txt": collection_root / "txt" / f"{episode}.txt",
    }
    for source_name, target in targets.items():
        source = delivery / source_name
        if not source.is_file() or source.stat().st_size == 0:
            raise RuntimeError(f"Missing delivery file: {source}")
        target.parent.mkdir(parents=True, exist_ok=True)
        temporary = target.with_suffix(target.suffix + ".tmp")
        shutil.copy2(source, temporary)
        temporary.replace(target)
    return job_root


def _safe_ingest_metadata(ingest: dict[str, object]) -> dict[str, object]:
    allowed = {
        "uid",
        "resolver_type",
        "media_profile",
        "media_size_bytes",
        "media_sha256",
        "duration_seconds",
        "container",
        "audio_codec",
        "video_codec",
        "reused_verified_media",
    }
    return {key: value for key, value in ingest.items() if key in allowed}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", required=True)
    parser.add_argument("--episode", required=True, type=int)
    parser.add_argument("--expected-uid", default="")
    parser.add_argument("--title", default="")
    parser.add_argument("--collection-root", type=Path, required=True)
    parser.add_argument("--work-root", type=Path, default=Path("worker-output"))
    parser.add_argument("--resolver-only", action="store_true")
    args = parser.parse_args()

    if not 1 <= args.episode <= 26:
        raise SystemExit("episode must be 1..26")

    if args.resolver_only:
        resolved = resolve_aparat_media(
            args.url,
            expected_uid=args.expected_uid or None,
        )
        print(
            json.dumps(
                {
                    "episode": args.episode,
                    "uid": resolved.uid,
                    "resolver_type": resolved.resolver_type,
                    "media_profile": resolved.profile,
                    "duration_seconds": resolved.duration_seconds,
                    "status": "resolved",
                },
                ensure_ascii=False,
            )
        )
        return

    worker_started = time.monotonic()
    args.work_root.mkdir(parents=True, exist_ok=True)
    args.collection_root.mkdir(parents=True, exist_ok=True)
    ledger = AsreShirinCheckpoints(args.work_root / "asre-shirin-checkpoints.json")
    ingest_root = args.work_root / "ingest" / f"episode-{args.episode}"
    media_path = ingest_root / "media.mp4"
    media_metadata_path = ingest_root / "media.json"
    try:
        ingest = ensure_verified_aparat_media(
            args.url,
            media_path,
            media_metadata_path,
            expected_uid=args.expected_uid or None,
        )
        ledger.mark_complete(
            "media_downloaded_verified",
            [media_path, media_metadata_path],
            _safe_ingest_metadata(ingest),
        )
    except Exception as exc:
        ledger.mark_failed("media_downloaded_verified", exc)
        raise

    pipeline_root = args.work_root / "pipeline"
    pipeline = _pipeline(media_path, pipeline_root, args.episode)
    role_outputs = [
        args.collection_root / "md" / f"{args.episode}.md",
        args.collection_root / "timestamped" / f"{args.episode}.md",
        args.collection_root / "txt" / f"{args.episode}.txt",
        args.collection_root / "roles" / f"{args.episode}.json",
    ]
    artifact_prepare_seconds = 0.0
    role_mapping_seconds = float(
        (ledger.data["stages"]["role_mapping_complete"].get("details") or {}).get(
            "role_mapping_seconds", 0.0
        )
    )
    role_completed_now = False

    if not ledger.is_complete("role_mapping_complete"):
        if not ledger.is_complete("diarization_complete"):
            status = run_pipeline(
                media_path,
                args.url,
                args.episode,
                args.title,
                pipeline_root,
            )
            pipeline = _pipeline(media_path, pipeline_root, args.episode)
            _sync_compute_checkpoints(ledger, pipeline)
            if status != 0:
                if not ledger.is_complete("diarization_complete"):
                    ledger.mark_failed("diarization_complete", f"pipeline_return_code_{status}")
                raise SystemExit(status)
        else:
            _sync_compute_checkpoints(ledger, pipeline)

        artifact_prepare_started = time.monotonic()
        copy_delivery(pipeline.paths.job_root, args.collection_root, args.episode)
        role_started = time.monotonic()
        try:
            subprocess.run(
                [
                    sys.executable,
                    "scripts/label_asre_shirin_roles.py",
                    str(args.collection_root),
                    str(args.episode),
                ],
                check=True,
            )
        except Exception as exc:
            ledger.mark_failed("role_mapping_complete", exc)
            raise
        role_mapping_seconds = time.monotonic() - role_started
        artifact_prepare_seconds = time.monotonic() - artifact_prepare_started
        role_completed_now = True

    role_path = args.collection_root / "roles" / f"{args.episode}.json"
    diarization_path = pipeline.paths.job_root / "diarization" / "diarization.json"
    role_data = json.loads(role_path.read_text(encoding="utf-8"))
    report = json.loads(diarization_path.read_text(encoding="utf-8"))
    role_data["diarization_report"] = {
        "backend": report.get("backend"),
        "raw_speaker_count": report.get("raw_speaker_count")
        or len(report.get("raw_speakers") or []),
        "aligned_effective_speaker_count": report.get("aligned_effective_speaker_count"),
        "aligned_effective_speakers": report.get("aligned_effective_speakers"),
        "requested_speaker_count": report.get("requested_speaker_count"),
        "stability": report.get("stability"),
    }
    role_path.write_text(
        json.dumps(role_data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    if role_completed_now:
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
        total_worker_seconds=time.monotonic() - worker_started,
    )
    timings = args.collection_root / "timings"
    timings.mkdir(parents=True, exist_ok=True)
    timing_path = timings / f"{args.episode}.json"
    timing_path.write_text(
        json.dumps(timing, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )

    sources = args.collection_root / "sources"
    sources.mkdir(parents=True, exist_ok=True)
    source_path = sources / f"{args.episode}.json"
    source_payload = {
        "episode": args.episode,
        "url": args.url,
        "title": args.title or f"سواد مالی در عصر شیرین | قسمت {args.episode}",
        "publisher": "fintelligence",
        "platform": "Aparat",
        "media": _safe_ingest_metadata(ingest),
        "compute_handoff": "run-file",
        "asr_model": "large-v3-turbo",
        "profile": "balanced",
        "device": "cpu",
        "compute_type": "int8",
        "diarization": "pyannote-community-1-auto-speaker-count",
        "external_ai_review": False,
    }
    source_path.write_text(
        json.dumps(source_payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )

    final_outputs = [*role_outputs, source_path, timing_path]
    ledger.mark_complete(
        "delivery_complete",
        final_outputs,
        {"total_worker_seconds": timing["total_worker_seconds"]},
    )
    print(
        json.dumps(
            {
                "episode": args.episode,
                "status": "complete",
                "compute_handoff": "run-file",
                "timing": timing,
            },
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    os.environ.setdefault("AI_REVIEW_ENABLED", "false")
    main()
