#!/usr/bin/env python3
"""Four independent Persian ASR jobs from one specifically named GitHub Release.

This is a machine-transcription stage only. Reviewed Markdown is produced later,
without overwriting the source transcript, and must be checked against audio.
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import urllib.parse
import urllib.request

from vid_pipeline.media import MEDIA_EXTENSIONS

REPOSITORY = "Shahbazi-Amir/vid_pipeline"
TAG = os.environ.get("AUDIO_RELEASE_TAG", "dars")
INDICES = ("01", "02", "03", "04")
# Pin the four uploaded media assets to avoid accidentally processing unrelated
# documents or a similarly named replacement upload in the same release.
EXPECTED_ASSETS = {
    "01": {"name": "1.m4a", "id": 721947299, "size": 51673324,
           "digest": "sha256:4629634e8aa9f5d1eda28b8f4543b060d6592f2c18adc1a8b1b024e572135798"},
    "02": {"name": "2.m4a", "id": 721940206, "size": 57159959,
           "digest": "sha256:d00636f786ed65c392a24b74b60c5cd952642231dcc1a538ec6586d75f5812a5"},
    "03": {"name": "3.m4a", "id": 721942695, "size": 61730613,
           "digest": "sha256:c50b551f0da376a239b7205a0eea798acc34d60660cab16b09b0376f700280b4"},
    "04": {"name": "4.m4a", "id": 721944616, "size": 68599269,
           "digest": "sha256:5bb127235a6d702888044aaaedd072ce863864abfde6929489a29372d06bac15"},
}
MAX_BYTES = 2 * 1024 ** 3


def github_json(url: str) -> dict:
    headers = {"Accept": "application/vnd.github+json", "User-Agent": "vid-pipeline-four-audio"}
    token = os.environ.get("GH_TOKEN", "")
    if token:
        headers["Authorization"] = "Bearer " + token
    with urllib.request.urlopen(urllib.request.Request(url, headers=headers), timeout=90) as response:
        return json.load(response)


def release_assets() -> tuple[dict, dict[str, dict]]:
    url = ("https://api.github.com/repos/" + REPOSITORY + "/releases/tags/"
           + urllib.parse.quote(TAG, safe=""))
    release = github_json(url)
    if release.get("draft") or release.get("tag_name") != TAG:
        raise RuntimeError("Release must be published and must use the exact configured tag")
    selected: dict[str, dict] = {}
    for asset in release.get("assets") or []:
        name = str(asset.get("name", ""))
        number = next((index for index, expected in EXPECTED_ASSETS.items()
                       if expected["name"] == name), None)
        if number is None:
            continue  # Non-audio assets (PDF, PPTX, HTML, etc.) are ignored.
        expected = EXPECTED_ASSETS[number]
        if number in selected:
            raise RuntimeError("Duplicate audio index: " + number)
        size = int(asset.get("size") or 0)
        if (os.path.splitext(name)[1].lower() not in MEDIA_EXTENSIONS
                or asset.get("state") != "uploaded"
                or not 0 < size <= MAX_BYTES
                or int(asset.get("id") or 0) != expected["id"]
                or size != expected["size"]
                or str(asset.get("digest") or "") != expected["digest"]):
            raise RuntimeError("Audio release asset differs from verified upload: " + name)
        if not asset.get("browser_download_url"):
            raise RuntimeError("Release download URL missing: " + name)
        selected[number] = asset
    if set(selected) != set(INDICES):
        raise RuntimeError("Expected these four verified audio assets: 1.m4a, 2.m4a, "
                           "3.m4a, 4.m4a. Found: " + ", ".join(sorted(selected)))
    return release, selected


def download(asset: dict, destination: Path) -> str:
    digest = hashlib.sha256()
    written = 0
    request = urllib.request.Request(
        str(asset["browser_download_url"]),
        headers={"User-Agent": "vid-pipeline-four-audio", "Accept": "application/octet-stream"},
    )
    with urllib.request.urlopen(request, timeout=150) as response, destination.open("wb") as target:
        while True:
            chunk = response.read(1024 * 1024)
            if not chunk:
                break
            written += len(chunk)
            if written > MAX_BYTES or written > int(asset["size"]):
                raise RuntimeError("Downloaded media exceeds declared size")
            digest.update(chunk)
            target.write(chunk)
    if written != int(asset["size"]):
        raise RuntimeError("Downloaded media size differs from GitHub Release metadata")
    actual = digest.hexdigest()
    expected = str(asset.get("digest") or "")
    if expected.startswith("sha256:") and actual != expected.removeprefix("sha256:"):
        raise RuntimeError("Downloaded media SHA-256 differs from GitHub Release metadata")
    return actual


def transcribe(number: str) -> None:
    if number not in INDICES:
        raise ValueError("Expected an index 01..04")
    output = Path("four-audio-results") / number
    output.mkdir(parents=True, exist_ok=True)
    try:
        release, items = release_assets()
        asset = items[number]
        media = Path("source-audio" + Path(asset["name"]).suffix.lower())
        sha256 = download(asset, media)
        provenance = {
            "repository": REPOSITORY,
            "release": release.get("html_url"),
            "release_name": release.get("name"),
            "release_tag": TAG,
            "release_id": release["id"],
            "asset_id": asset["id"],
            "asset_name": asset["name"],
            "bytes": asset["size"],
            "sha256": sha256,
            "source_commit": os.environ.get("GITHUB_SHA", ""),
            "model": "large-v3-turbo",
            "language": "fa",
            "processing": "independent_machine_transcription",
            "audio_review": "not_performed",
        }
        (output / "source.json").write_text(
            json.dumps(provenance, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
        cmd = [
            sys.executable, "-m", "vid_pipeline.cli", "run-file", str(media),
            "--name", "persian-audio-" + number, "--output-root", "four-audio-work",
            "--profile", "balanced", "--model", "large-v3-turbo", "--language", "fa",
            "--device", "cpu", "--compute-type", "int8", "--audio-profile", "safe",
            "--no-editorial",
        ]
        with (output / "worker.log").open("w", encoding="utf-8") as log:
            result = subprocess.run(cmd, stdout=log, stderr=subprocess.STDOUT, check=False)
        if result.returncode:
            raise RuntimeError("Pipeline failed, exit status " + str(result.returncode))

        required = (
            ("*/final/transcript.final.md", "transcript.md"),
            ("*/final/transcript.final.txt", "transcript.txt"),
            ("*/raw/transcript.raw.md", "transcript.timestamped.md"),
            ("*/raw/transcript.raw.json", "transcript.raw.json"),
        )
        for pattern, name in required:
            matches = list(Path("four-audio-work").glob(pattern))
            if len(matches) != 1 or matches[0].stat().st_size == 0:
                raise RuntimeError("Missing or ambiguous transcript output: " + pattern)
            shutil.copyfile(matches[0], output / name)
        raw = json.loads((output / "transcript.raw.json").read_text(encoding="utf-8"))
        if not raw.get("segments") or not (output / "transcript.txt").read_text(
            encoding="utf-8"
        ).strip():
            raise RuntimeError("ASR produced an empty transcript")
        status = {
            "state": "machine_transcription_complete",
            "review": "pending_audio_and_text_verification",
            "segment_count": len(raw["segments"]),
            "audio_duration_seconds": raw.get("duration"),
        }
        (output / "status.json").write_text(
            json.dumps(status, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
        print(f"Transcribed {number}: {asset['name']} ({len(raw['segments'])} segments)", flush=True)
    except Exception as exc:
        (output / "status.json").write_text(
            json.dumps({"state": "failed", "error": str(exc)}, ensure_ascii=False, indent=2)
            + "\n", encoding="utf-8"
        )
        raise


def main() -> None:
    if len(sys.argv) != 2:
        raise SystemExit("Usage: transcribe_four_release.py verify | 01 | 02 | 03 | 04")
    if sys.argv[1] == "verify":
        release, assets = release_assets()
        print("Release verified:", release.get("html_url"))
        for number, asset in sorted(assets.items()):
            print(number, asset["name"], asset["size"], "bytes")
    else:
        transcribe(sys.argv[1])


if __name__ == "__main__":
    main()
