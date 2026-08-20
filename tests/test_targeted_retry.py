from __future__ import annotations

from pathlib import Path

from vid_pipeline.targeted_retry import build_targeted_retry_candidates
from vid_pipeline.transcribe import TranscriptionConfig


def _segment(identifier: int, confidence: float, *, flags: list[str] | None = None) -> dict:
    return {
        "id": identifier,
        "start": float(identifier),
        "end": float(identifier + 1),
        "text": f"متن {identifier}",
        "avg_logprob": -0.2,
        "no_speech_prob": 0.0,
        "review_flags": list(flags or []),
        "words": [{"word": "متن", "probability": confidence}],
    }


def test_fast_profile_performs_no_retry(tmp_path: Path) -> None:
    calls = 0

    def runner(*_args, **_kwargs):
        nonlocal calls
        calls += 1
        return {"text": "x", "confidence": 1.0}

    report = build_targeted_retry_candidates(
        tmp_path / "audio.wav",
        {"segments": [_segment(1, 0.1, flags=["low_word_confidence"])]},
        profile="fast",
        work_dir=tmp_path,
        config=TranscriptionConfig(),
        runner=runner,
    )
    assert report["full_file_additional_passes"] == 0
    assert report["targeted_segment_count"] == 0
    assert calls == 0


def test_balanced_retries_only_suspicious_segments(tmp_path: Path) -> None:
    called: list[int] = []

    def runner(_clip, segment, _policy, _config):
        called.append(segment["id"])
        return {"text": segment["text"] + " اصلاح", "confidence": 0.95}

    report = build_targeted_retry_candidates(
        tmp_path / "audio.wav",
        {
            "segments": [
                _segment(1, 0.98),
                _segment(2, 0.45, flags=["low_word_confidence"]),
                _segment(3, 0.92),
            ]
        },
        profile="balanced",
        work_dir=tmp_path,
        config=TranscriptionConfig(),
        runner=runner,
    )
    assert report["full_file_additional_passes"] == 0
    assert report["targeted_segment_count"] == 1
    assert called == [2]
    assert report["items"][0]["requires_review"] is True


def test_accurate_profile_caps_targeted_work(tmp_path: Path) -> None:
    calls = 0

    def runner(_clip, segment, _policy, _config):
        nonlocal calls
        calls += 1
        return {"text": segment["text"], "confidence": 0.9}

    rows = [_segment(index, 0.2, flags=["low_word_confidence"]) for index in range(150)]
    report = build_targeted_retry_candidates(
        tmp_path / "audio.wav",
        {"segments": rows},
        profile="accurate",
        work_dir=tmp_path,
        config=TranscriptionConfig(),
        runner=runner,
    )
    assert report["targeted_segment_count"] == 120
    assert calls == 120
