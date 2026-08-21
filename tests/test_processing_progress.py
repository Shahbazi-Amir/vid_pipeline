from __future__ import annotations

import json
from pathlib import Path

from vid_pipeline.server.processing import process_media_core


def test_processing_core_reports_detailed_stages(tmp_path: Path, monkeypatch) -> None:
    import vid_pipeline.server.processing as module

    media = tmp_path / "input.mp4"
    media.write_bytes(b"media")
    stages: list[tuple[str, int]] = []

    def fake_normalize(_media, output, **kwargs):
        Path(output).write_bytes(b"wav")
        Path(kwargs["quality_path"]).write_text('{"duration_seconds": 12.5}', encoding="utf-8")
        return Path(output)

    def fake_transcribe(_audio, raw_json, raw_md, config):
        payload = {
            "duration": 12.5,
            "model": config.model,
            "segments": [{
                "id": 1, "start": 0.0, "end": 12.0, "text": "سلام دنیا",
                "words": [{"word": "سلام", "probability": 0.97}],
                "review_flags": [], "avg_logprob": -0.1, "no_speech_prob": 0.0,
            }],
        }
        Path(raw_json).write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
        Path(raw_md).write_text("سلام دنیا", encoding="utf-8")
        return payload

    def fake_retry(*_args, **_kwargs):
        return {"full_file_additional_passes": 0, "targeted_segment_count": 0, "candidate_count": 0, "items": []}

    def fake_write(report, path):
        Path(path).write_text(json.dumps(report), encoding="utf-8")
        return Path(path)

    def fake_clean(_raw, md, txt, **_kwargs):
        Path(md).write_text("سلام دنیا", encoding="utf-8")
        Path(txt).write_text("سلام دنیا", encoding="utf-8")

    monkeypatch.setattr(module, "normalize_audio", fake_normalize)
    monkeypatch.setattr(module, "transcribe_audio", fake_transcribe)
    monkeypatch.setattr(module, "build_targeted_retry_candidates", fake_retry)
    monkeypatch.setattr(module, "write_targeted_retry_report", fake_write)
    monkeypatch.setattr(module, "clean_transcript", fake_clean)
    monkeypatch.setattr(module, "evaluate_transcript_quality", lambda *_args: {
        "valid": True, "decision": "pass", "overall_score": 91, "gate_reasons": []
    })

    result = process_media_core(
        media,
        {"job_id": "job-1", "profile": "balanced", "model": "large-v3-turbo", "language": "fa"},
        tmp_path / "work",
        stage_callback=lambda name, progress: stages.append((name, progress)),
    )

    assert stages == [
        ("normalize_audio", 25),
        ("transcribe_primary", 35),
        ("targeted_retry", 60),
        ("clean_transcript", 70),
        ("quality_scoring", 78),
    ]
    assert result.raw_payload["duration"] == 12.5
    assert result.document.text == "سلام دنیا"
