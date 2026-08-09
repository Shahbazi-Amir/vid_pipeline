from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
from dataclasses import replace
from pathlib import Path

from vid_pipeline import pyannote_cli, reliable_cli


def run_pipeline(url: str, episode: int, title: str, output_root: Path) -> int:
    original_accuracy_config = reliable_cli._accuracy_config

    def automatic_speaker_accuracy_config(args):
        config = original_accuracy_config(args)
        return replace(config, num_speakers=None, speaker_role_mode="generic")

    reliable_cli._accuracy_config = automatic_speaker_accuracy_config
    original_argv = sys.argv[:]
    try:
        sys.argv = [
            "vid-pipeline",
            "run-url",
            url,
            "--source-url",
            url,
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
        ]
        return pyannote_cli.main()
    finally:
        reliable_cli._accuracy_config = original_accuracy_config
        sys.argv = original_argv


def copy_delivery(output_root: Path, collection_root: Path, episode: int) -> Path:
    deliveries = [path for path in output_root.rglob("delivery") if path.is_dir()]
    if len(deliveries) != 1:
        raise RuntimeError(f"Expected exactly one delivery directory, found {len(deliveries)}")
    delivery = deliveries[0]
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
        shutil.copy2(source, target)
    return delivery.parent


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", required=True)
    parser.add_argument("--episode", required=True, type=int)
    parser.add_argument("--title", default="")
    parser.add_argument("--collection-root", type=Path, required=True)
    parser.add_argument("--work-root", type=Path, default=Path("worker-output"))
    args = parser.parse_args()

    if not 1 <= args.episode <= 26:
        raise SystemExit("episode must be 1..26")

    if args.work_root.exists():
        shutil.rmtree(args.work_root)
    args.work_root.mkdir(parents=True)
    args.collection_root.mkdir(parents=True, exist_ok=True)

    status = run_pipeline(args.url, args.episode, args.title, args.work_root)
    if status != 0:
        raise SystemExit(status)

    job_root = copy_delivery(args.work_root, args.collection_root, args.episode)

    subprocess.run(
        [
            sys.executable,
            "scripts/label_asre_shirin_roles.py",
            str(args.collection_root),
            str(args.episode),
        ],
        check=True,
    )

    sources = args.collection_root / "sources"
    sources.mkdir(parents=True, exist_ok=True)
    source_payload = {
        "episode": args.episode,
        "url": args.url,
        "title": args.title or f"سواد مالی در عصر شیرین | قسمت {args.episode}",
        "publisher": "fintelligence",
        "platform": "Aparat",
        "diarization": "pyannote-community-1-auto-speaker-count",
        "external_ai_review": False,
    }
    (sources / f"{args.episode}.json").write_text(
        json.dumps(source_payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )

    diarization = job_root / "diarization" / "diarization.json"
    if diarization.is_file():
        role_path = args.collection_root / "roles" / f"{args.episode}.json"
        role_data = json.loads(role_path.read_text(encoding="utf-8"))
        report = json.loads(diarization.read_text(encoding="utf-8"))
        role_data["diarization_report"] = {
            "backend": report.get("backend"),
            "raw_speaker_count": report.get("raw_speaker_count"),
            "aligned_effective_speaker_count": report.get("aligned_effective_speaker_count"),
            "aligned_effective_speakers": report.get("aligned_effective_speakers"),
            "requested_speaker_count": report.get("requested_speaker_count"),
            "stability": report.get("stability"),
        }
        role_path.write_text(json.dumps(role_data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    print(json.dumps({"episode": args.episode, "status": "complete", "url": args.url}, ensure_ascii=False))


if __name__ == "__main__":
    main()
