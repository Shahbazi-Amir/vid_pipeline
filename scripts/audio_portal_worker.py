#!/usr/bin/env python3
"""Run the same tested Quran lecture CLI for one durable portal job."""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "apps/audio_portal"))
from backend import BRANCH, GitHubPortal, PortalError, now, validate_job


def load_job(path):
    path = Path(path)
    if path.parent.as_posix() != ".portal/jobs" or path.suffix != ".json":
        raise ValueError("Unexpected request path")
    job = validate_job(json.loads(path.read_text(encoding="utf-8")))
    if path.stem != job["id"]:
        raise ValueError("Job filename/id mismatch")
    return job


def status(gh, job, state):
    data = {"state": state, "updated_at": now(), "review": "pending_audio_and_quran_verification",
            "run_url": f"https://github.com/{gh.repository}/actions/runs/{os.environ.get('GITHUB_RUN_ID', '')}"}
    gh.write(f"outputs/audio-portal/{job['id']}/status.json", json.dumps(data, indent=2) + "\n",
             f"Audio portal status {job['id']}: {state}", replace=True)


def command(job, media):
    prompt = ("گفتار فارسی همراه با نقل قول عربی و آیات قرآن کریم. نقل قول عربی را به زبان عربی بنویس."
              if job["language"] == "fa" else "خطاب عربي مع اقتباسات من القرآن الكريم.")
    return [sys.executable, "-m", "vid_pipeline.cli", "run-file", str(media),
            "--name", job["id"], "--output-root", "portal-work", "--profile", "balanced",
            "--model", "large-v3-turbo", "--language", job["language"], "--device", "cpu",
            "--compute-type", "int8", "--audio-profile", "safe", "--no-editorial", "--initial-prompt", prompt]


def run(gh, job):
    previous = gh.read(f"outputs/audio-portal/{job['id']}/status.json")
    if previous and json.loads(previous["data"])["state"] == "completed":
        print("Job already completed; original outputs preserved.")
        return
    release = gh.release()
    asset = next((a for a in gh.assets(release["id"]) if a["id"] == job["asset_id"]), None)
    # Retry requests may reuse a prior portal asset, but never an unrelated release asset.
    if not asset or not asset["name"].startswith("portal-") or not asset["name"].endswith(job["suffix"]) or asset["size"] != job["size"]:
        raise PortalError("Source asset is not a matching portal upload in the configured release")
    status(gh, job, "downloading")
    media = Path("portal-input" + job["suffix"])
    gh.download_asset(job["asset_id"], media, job["size"], job["sha256"])
    status(gh, job, "transcribing")
    result = subprocess.run(command(job, media), check=False)
    if result.returncode:
        raise RuntimeError("ASR worker exited unsuccessfully")
    status(gh, job, "publishing")
    output = Path("portal-results")
    output.mkdir(exist_ok=True)
    mapping = {
        "*/final/transcript.final.md": "transcript.md",
        "*/final/transcript.final.txt": "transcript.txt",
        "*/raw/transcript.raw.md": "transcript.timestamped.md",
        "*/raw/transcript.raw.json": "transcript.raw.json",
    }
    for pattern, target in mapping.items():
        matches = list(Path("portal-work").glob(pattern))
        if len(matches) != 1 or not matches[0].stat().st_size:
            raise RuntimeError("Missing or ambiguous output: " + pattern)
        shutil.copyfile(matches[0], output / target)
    if not (output / "transcript.txt").read_text(encoding="utf-8").strip():
        raise RuntimeError("Transcript is empty")
    (output / "source.json").write_text(json.dumps({**job, "source_commit": os.getenv("GITHUB_SHA"),
        "model": "large-v3-turbo", "kind": "machine_draft", "reviewed": False}, ensure_ascii=False, indent=2), encoding="utf-8")
    for file in sorted(output.iterdir()):
        gh.write(f"outputs/audio-portal/{job['id']}/{file.name}", file.read_bytes(), f"Save audio draft {job['id']}")
    status(gh, job, "completed")
    print("Machine draft saved; audio and Quran verification remain pending.")


def main():
    mode, path = sys.argv[1:]
    job = load_job(path)
    if os.getenv("GITHUB_REF_NAME", BRANCH) != BRANCH:
        raise ValueError("Worker is limited to the portal branch")
    gh = GitHubPortal(os.environ["GH_TOKEN"], os.environ["GITHUB_REPOSITORY"])
    try:
        if mode == "run":
            run(gh, job)
        elif mode == "preparing":
            existing = gh.read(f"outputs/audio-portal/{job['id']}/status.json")
            if not existing:
                status(gh, job, "preparing")
        elif mode == "fail":
            existing = gh.read(f"outputs/audio-portal/{job['id']}/status.json")
            if not existing or json.loads(existing["data"])["state"] != "completed":
                status(gh, job, "failed")
        else:
            raise ValueError("Unsupported worker mode")
    finally:
        gh.close()


if __name__ == "__main__":
    main()
