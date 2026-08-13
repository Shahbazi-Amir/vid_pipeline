from __future__ import annotations

import hashlib
import json
from pathlib import Path

from vid_pipeline.chatgpt_handoff import build_chatgpt_handoff


def _write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def test_build_chatgpt_handoff_is_complete_api_free_and_lossless(tmp_path: Path) -> None:
    machine = ("بخش اول متن.\n\nبخش دوم متن.\n\n" * 100).strip() + "\n"
    _write(tmp_path / "source.json", json.dumps({"source": "local_file"}))
    _write(tmp_path / "raw" / "transcript.raw.json", '{"segments": []}')
    _write(tmp_path / "raw" / "transcript.raw.md", "# خام\n")
    _write(tmp_path / "machine" / "transcript.machine.md", "# ماشینی\n" + machine)
    _write(tmp_path / "machine" / "transcript.machine.txt", machine)
    _write(tmp_path / "audio" / "audio-quality.json", '{"warnings": []}')
    _write(tmp_path / "diarization" / "diarization.json", '{"speakers": []}')
    _write(tmp_path / "result.json", '{"status": "machine_processing_complete"}')

    details = build_chatgpt_handoff(tmp_path, chunk_chars=1000)
    package = Path(details["package"])
    manifest = json.loads((package / "review-manifest.json").read_text(encoding="utf-8"))
    chunks = manifest["chunk_strategy"]["chunks"]

    assert details["paid_api_invoked"] is False
    assert manifest["paid_api_invoked"] is False
    assert {"audio-quality.json", "diarization.json"} <= set(
        manifest["optional_files_included"]
    )
    rebuilt = "".join((package / item["path"]).read_text(encoding="utf-8") for item in chunks)
    assert rebuilt == machine
    assert hashlib.sha256(rebuilt.encode()).hexdigest() == manifest["source_transcript_sha256"]
    prompt = (package / "chatgpt-review-prompt.md").read_text(encoding="utf-8")
    assert "اطلاعات تازه نساز" in prompt
    assert "حدس نزن" in prompt
    result = json.loads((tmp_path / "result.json").read_text(encoding="utf-8"))
    assert result["chatgpt_review_status"] == "ready"


def test_chatgpt_handoff_rebuild_replaces_stale_files(tmp_path: Path) -> None:
    for relative, content in {
        "source.json": "{}",
        "raw/transcript.raw.json": "{}",
        "raw/transcript.raw.md": "raw",
        "machine/transcript.machine.md": "machine",
        "machine/transcript.machine.txt": "short",
    }.items():
        _write(tmp_path / relative, content)
    _write(tmp_path / "review" / "chatgpt" / "stale.txt", "stale")

    build_chatgpt_handoff(tmp_path)

    assert not (tmp_path / "review" / "chatgpt" / "stale.txt").exists()
