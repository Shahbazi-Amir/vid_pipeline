from __future__ import annotations

import json
from pathlib import Path

from vid_pipeline.accuracy import AccuracyConfig, PassSpec, build_accuracy_package
from vid_pipeline.pre_review import build_pre_review_package
from vid_pipeline.review import ReviewConfig, build_review_package
from vid_pipeline.state import PipelineState


def test_fake_asr_retries_only_low_confidence_segment(tmp_path: Path, monkeypatch) -> None:
    job = tmp_path / "job"
    for name in ("raw", "audio", "machine", "final"):
        (job / name).mkdir(parents=True, exist_ok=True)
    raw = {
        "language": "fa", "duration": 4, "model": "large-v3-turbo",
        "segments": [
            {"id": 0, "start": 0, "end": 2, "text": "نام شرکت مبهم است",
             "avg_logprob": -1.2, "no_speech_prob": 0.01, "compression_ratio": 1.0,
             "words": [{"word": "مبهم", "probability": 0.2}]},
            {"id": 1, "start": 2, "end": 4, "text": "این بخش روشن است",
             "avg_logprob": -0.1, "no_speech_prob": 0.01, "compression_ratio": 1.0,
             "words": [{"word": "روشن", "probability": 0.98}]},
        ],
    }
    (job / "raw" / "transcript.raw.json").write_text(json.dumps(raw, ensure_ascii=False), encoding="utf-8")
    (job / "audio" / "audio-16k-mono.wav").write_bytes(b"fake")
    text = "نام شرکت مبهم است\n\nاین بخش روشن است\n"
    (job / "machine" / "transcript.machine.txt").write_text(text, encoding="utf-8")
    (job / "final" / "transcript.final.txt").write_text(text, encoding="utf-8")
    (job / "result.json").write_text(json.dumps({"status": "machine_processing_complete"}), encoding="utf-8")
    PipelineState(job / "state.json").save()
    calls: list[str] = []
    monkeypatch.setattr("vid_pipeline.accuracy.extract_clip", lambda *args, **kwargs: "")

    def runner(path: Path, spec: PassSpec, hotwords: str) -> dict:
        calls.append(path.name)
        return {"model": spec.model, "segments": [{"start": 0, "end": 2,
                "text": "نام شرکت مبهم است", "avg_logprob": -0.1,
                "no_speech_prob": 0.0, "words": [{"probability": 0.95}]}]}

    manifest = build_accuracy_package(job, config=AccuracyConfig(mode="fast"), pass_runner=runner)
    build_pre_review_package(job)
    review = build_review_package(job, config=ReviewConfig(extract_clips=False))
    result = json.loads((job / "result.json").read_text(encoding="utf-8"))
    state = json.loads((job / "state.json").read_text(encoding="utf-8"))

    assert manifest["targeted_segment_count"] == 1
    assert calls == ["segment-0000.wav"]
    assert review["status"] == result["status"] == "human_review_required"
    assert result["accuracy_kind"] == "reference_free_quality"
    assert all(state["stages"][name]["status"] == "completed" for name in ("accuracy", "pre_review", "review"))
