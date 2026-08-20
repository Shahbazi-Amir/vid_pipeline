from __future__ import annotations

import json
from pathlib import Path

from vid_pipeline.server.processing import process_media_core


def test_canonical_core_runs_one_primary_asr_and_targeted_policy(tmp_path: Path, monkeypatch) -> None:
    import vid_pipeline.server.processing as module

    media = tmp_path / "input.mp4"
    media.write_bytes(b"media")
    calls: list[str] = []

    def fake_normalize(_media, output, **kwargs):
        calls.append("normalize")
        Path(output).write_bytes(b"wav")
        Path(kwargs["quality_path"]).write_text("{}", encoding="utf-8")
        return Path(output)

    def fake_transcribe(_audio, raw_json, raw_md, config):
        calls.append("primary_asr")
        payload = {
            "model": config.model,
            "segments": [
                {
                    "id": 1,
                    "start": 0,
                    "end": 1,
                    "text": "سلام",
                    "words": [{"word": "سلام", "probability": 0.95}],
                    "review_flags": [],
                    "avg_logprob": -0.1,
                    "no_speech_prob": 0.0,
                }
            ],
        }
        Path(raw_json).write_text(json.dumps(payload), encoding="utf-8")
        Path(raw_md).write_text("سلام", encoding="utf-8")
        return payload

    def fake_retry(_audio, _payload, *, profile, **_kwargs):
        calls.append(f"retry:{profile}")
        return {
            "full_file_additional_passes": 0,
            "targeted_segment_count": 0,
            "candidate_count": 0,
            "items": [],
        }

    def fake_clean(_raw, md, txt, **_kwargs):
        calls.append("clean")
        Path(md).write_text("سلام", encoding="utf-8")
        Path(txt).write_text("سلام", encoding="utf-8")
        return {}

    monkeypatch.setattr(module, "normalize_audio", fake_normalize)
    monkeypatch.setattr(module, "transcribe_audio", fake_transcribe)
    monkeypatch.setattr(module, "build_targeted_retry_candidates", fake_retry)
    monkeypatch.setattr(module, "clean_transcript", fake_clean)
    monkeypatch.setattr(
        module,
        "evaluate_transcript_quality",
        lambda *_args: {"valid": True, "decision": "pass", "overall_score": 90, "gate_reasons": []},
    )

    result = process_media_core(
        media,
        {
            "job_id": "job-1",
            "profile": "balanced",
            "model": "large-v3-turbo",
            "language": "fa",
            "audio_profile": "safe",
            "file_name": "input.mp4",
        },
        tmp_path / "work",
    )

    assert calls == ["normalize", "primary_asr", "retry:balanced", "clean"]
    assert result.quality_report["targeted_retry"]["full_file_additional_passes"] == 0
    assert result.document.text == "سلام"
    assert (tmp_path / "work" / "core-manifest.json").is_file()
