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
    assert "**گوینده نامشخص**" in rendered


def test_better_coarse_text_does_not_collapse_finer_speaker_timeline(tmp_path: Path) -> None:
    root = _job(tmp_path)
    _write_json(root / "human/verification.json", {
        "segments": [{"start": 0, "end": 10, "reviewed_text": "متن بازبینی‌شده"}]
    })
    consensus = root / "accuracy/transcript.consensus.json"
    _write_json(consensus, {"segments": [
        {"start": 0, "end": 5, "text": "سلام", "speaker": "SPEAKER_00"},
        {"start": 5, "end": 10, "text": "پاسخ", "speaker": "SPEAKER_01"},
    ]})
    result = export_final_outputs(root)
    timestamped = (root / "delivery/transcript.timestamped.md").read_text(encoding="utf-8")
    assert "گوینده ۱" in timestamped
    assert "گوینده ۲" in timestamped
    assert result["timestamp_source"] == str(consensus.resolve())


def test_required_export_rejects_speaker_collapse(tmp_path: Path) -> None:
    root = _job(tmp_path)
    _write_json(root / "accuracy/transcript.consensus.json", {
        "segments": [{"start": 0, "end": 10, "text": "فقط یک نفر", "speaker": "SPEAKER_00"}]
    })
    _write_json(root / "diarization/diarization.json", {
        "requested_speaker_count": 2,
        "aligned_effective_speakers": ["SPEAKER_00", "SPEAKER_01"],
        "config": {"required": True},
    })
    with pytest.raises(ValueError, match=r"requested=2.*exported_effective=1"):
        export_final_outputs(root)
    assert not (root / "delivery").exists()
