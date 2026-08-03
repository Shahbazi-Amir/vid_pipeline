from __future__ import annotations

import json
from pathlib import Path

import pytest

from vid_pipeline.final_export import OUTPUT_NAMES, export_final_outputs, render_timestamped
from vid_pipeline.state import PipelineState


def _write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False), encoding="utf-8")


def _job(tmp_path: Path) -> Path:
    final = tmp_path / "final"
    final.mkdir()
    (final / "transcript.final.md").write_text("# عنوان\n\nمتن نهایی\n", encoding="utf-8")
    (final / "transcript.final.txt").write_text("متن نهایی\n", encoding="utf-8")
    _write_json(tmp_path / "result.json", {"status": "completed"})
    PipelineState(tmp_path / "state.json").save()
    return tmp_path


def test_export_contains_exactly_three_user_files_and_prefers_consensus(tmp_path: Path) -> None:
    root = _job(tmp_path)
    _write_json(root / "raw/transcript.raw.json", {"segments": [{"start": 1, "end": 2, "text": "raw"}]})
    consensus = root / "accuracy/transcript.consensus.json"
    _write_json(consensus, {"segments": [{"start": 4, "end": 11, "text": "متن اجماع"}]})
    result = export_final_outputs(root)
    delivery = root / "delivery"
    assert {item.name for item in delivery.iterdir()} == set(OUTPUT_NAMES)
    timestamped = (delivery / "transcript.timestamped.md").read_text(encoding="utf-8")
    assert "[00:00:04 → 00:00:11]" in timestamped
    assert "متن اجماع" in timestamped
    assert result["timestamp_source"] == str(consensus.resolve())
    state = json.loads((root / "state.json").read_text(encoding="utf-8"))
    assert state["stages"]["export"]["status"] == "completed"


def test_export_falls_back_to_raw_and_keeps_debug_files(tmp_path: Path) -> None:
    root = _job(tmp_path)
    _write_json(root / "raw/transcript.raw.json", {"segments": [{"start": 0, "end": 3, "text": "fallback"}]})
    (root / "audio").mkdir()
    (root / "audio/audio.wav").write_bytes(b"debug")
    export_final_outputs(root)
    assert "fallback" in (root / "delivery/transcript.timestamped.md").read_text(encoding="utf-8")
    assert (root / "audio/audio.wav").exists()


def test_export_refuses_to_invent_timestamps(tmp_path: Path) -> None:
    root = _job(tmp_path)
    _write_json(root / "raw/transcript.raw.json", {"segments": [{"text": "untimed"}]})
    with pytest.raises(ValueError, match="valid, real segment timestamps"):
        export_final_outputs(root)


def test_timestamp_renderer_supports_more_than_one_hour() -> None:
    rendered = render_timestamped([{"start": 7215, "end": 7228, "text": "متن"}])
    assert "[02:00:15 → 02:00:28]" in rendered
