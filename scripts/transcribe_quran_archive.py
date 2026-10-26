#!/usr/bin/env python3
"""Transcribe one verified member of the Quran lectures archive using the project CLI."""
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import urllib.request
import zipfile

NUMBER = sys.argv[1]
ROOT = Path("results") / NUMBER
ROOT.mkdir(parents=True, exist_ok=True)
archive = Path("Archive.zip")
url = "https://github.com/Shahbazi-Amir/vid_pipeline/releases/download/rag_finance/Archive.zip"
expected = "99f27334aad810f6202e8cc1a67d8949678b0e770ce0a0ed5fa01d58d79a59d6"
with urllib.request.urlopen(url, timeout=120) as response, archive.open("wb") as output:
    shutil.copyfileobj(response, output)
if hashlib.file_digest(archive.open("rb"), "sha256").hexdigest() != expected:
    raise RuntimeError("Archive SHA-256 mismatch")
with zipfile.ZipFile(archive) as bundle:
    candidates = []
    for member in bundle.infolist():
        if member.filename.startswith("__MACOSX/") or not member.filename.lower().endswith(".m4a"):
            continue
        name = member.filename
        if not member.flag_bits & 0x800:
            name = name.encode("cp437").decode("utf-8")
        candidates.append((name, member))
    if len(candidates) != 2:
        raise RuntimeError("Expected exactly two M4A files")
    candidates.sort(key=lambda pair: pair[0].translate(str.maketrans("۰۱۲۳۴۵۶۷۸۹", "0123456789")))
    name, member = candidates[int(NUMBER)-1]
    media = Path("input.m4a")
    with bundle.open(member) as source, media.open("wb") as output:
        shutil.copyfileobj(source, output)
metadata = {
    "source_url": url, "archive_sha256": expected, "member": name,
    "member_size": media.stat().st_size, "number": NUMBER,
    "source_commit": os.environ.get("GITHUB_SHA", ""),
    "review_status": "machine_transcript_pending_audio_and_quran_verification",
    "model": "large-v3-turbo", "language": "fa",
}
(ROOT / "source.json").write_text(json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8")
command = [
    sys.executable, "-m", "vid_pipeline.cli", "run-file", str(media),
    "--name", "quran-lecture-" + NUMBER, "--output-root", "work-output",
    "--profile", "balanced", "--model", "large-v3-turbo",
    "--language", "fa", "--device", "cpu", "--compute-type", "int8",
    "--audio-profile", "safe", "--no-editorial",
    "--initial-prompt", "گفتار فارسی همراه با نقل قول عربی و آیات قرآن کریم. نقل قول عربی را به زبان عربی بنویس.",
]
with (ROOT / "worker.log").open("w", encoding="utf-8") as log:
    result = subprocess.run(command, stdout=log, stderr=subprocess.STDOUT)
if result.returncode:
    raise SystemExit(result.returncode)
for pattern, target in [
    ("*/final/transcript.final.md", "transcript.md"),
    ("*/final/transcript.final.txt", "transcript.txt"),
    ("*/raw/transcript.raw.md", "transcript.timestamped.md"),
    ("*/raw/transcript.raw.json", "transcript.raw.json"),
]:
    matches = list(Path("work-output").glob(pattern))
    if len(matches) != 1 or not matches[0].stat().st_size:
        raise RuntimeError("Missing or ambiguous output: " + pattern)
    shutil.copyfile(matches[0], ROOT / target)
(ROOT / "status.json").write_text(json.dumps({"state": "machine_transcription_complete", "review": "pending_audio_and_quran_verification"}), encoding="utf-8")
print("Completed lecture", NUMBER, name, flush=True)
