from __future__ import annotations

import json
from pathlib import Path

from vid_pipeline.accuracy import (
    AccuracyConfig,
    PassSpec,
    build_accuracy_package,
    evaluate_corpus,
    evaluate_text,
    select_consensus,
)
from vid_pipeline.accuracy_review import apply_accuracy_review


def test_protected_names_require_majority() -> None:
    config = AccuracyConfig()
    two = select_consensus(
        [
            {
                "pass": "primary",
                "text": "شهید آله هاشم",
                "normalized": "شهید آله هاشم",
                "confidence": 0.7,
            },
            {
                "pass": "second",
                "text": "شهید آل هاشم",
                "normalized": "شهید آل هاشم",
                "confidence": 0.9,
            },
        ],
        config,
    )
    assert two["text"] == "شهید آله هاشم"
    assert two["requires_human"] is True
    three = select_consensus(
        [
            {
                "pass": "primary",
                "text": "شهید آله هاشم",
                "normalized": "شهید آله هاشم",
                "confidence": 0.7,
            },
            {
                "pass": "second",
                "text": "شهید آل هاشم",
                "normalized": "شهید آل هاشم",
                "confidence": 0.9,
            },
            {
                "pass": "targeted",
                "text": "شهید آل هاشم",
                "normalized": "شهید آل هاشم",
                "confidence": 0.95,
            },
        ],
        config,
    )
    assert three["text"] == "شهید آل هاشم"
    assert three["requires_human"] is True
    assert "protected_name_or_number_disagreement" in three["reasons"]


def test_build_package_with_injected_runner(tmp_path: Path, monkeypatch) -> None:
    job = tmp_path / "job"
    (job / "raw").mkdir(parents=True)
    (job / "audio").mkdir()
    (job / "audio" / "audio-16k-mono.wav").write_bytes(b"fake")
    raw = {
        "language": "fa",
        "duration": 3,
        "model": "small",
        "segments": [
            {
                "id": 0,
                "start": 0,
                "end": 3,
                "text": "شهید آله هاشم",
                "avg_logprob": -0.4,
                "words": [],
                "review_flags": ["low_word_confidence"],
            }
        ],
    }
    (job / "raw" / "transcript.raw.json").write_text(
        json.dumps(raw, ensure_ascii=False),
        encoding="utf-8",
    )
    (job / "result.json").write_text("{}", encoding="utf-8")
    monkeypatch.setattr("vid_pipeline.accuracy.extract_clip", lambda *args, **kwargs: "")

    def runner(path: Path, spec: PassSpec, hotwords: str) -> dict:
        return {
            "model": spec.model,
            "segments": [
                {
                    "start": 0,
                    "end": 3,
                    "text": "شهید آل هاشم",
                    "words": [{"probability": 0.95}],
                }
            ],
        }

    manifest = build_accuracy_package(
        job,
        config=AccuracyConfig(mode="balanced"),
        pass_runner=runner,
    )
    assert manifest["pass_count"] == 2
    consensus = json.loads(
        (job / "accuracy" / "transcript.consensus.json").read_text(encoding="utf-8")
    )
    assert consensus["segments"][0]["text"] == "شهید آل هاشم"
    assert evaluate_text("این یک متن است", "این متن است")["wer"] > 0


def test_apply_accuracy_review(tmp_path: Path) -> None:
    job = tmp_path / "job"
    directory = job / "accuracy"
    directory.mkdir(parents=True)
    (directory / "transcript.consensus.json").write_text(
        json.dumps(
            {
                "segments": [
                    {
                        "id": 1,
                        "start": 0,
                        "end": 1,
                        "text": "الف",
                        "review_flags": ["multi_pass_disagreement"],
                        "consensus": {},
                    }
                ]
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    (directory / "disagreements.json").write_text(
        json.dumps(
            {
                "items": [
                    {
                        "segment_id": 1,
                        "candidates": [{"text": "الف"}, {"text": "ب"}],
                    }
                ]
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    corrections = job / "corrections.json"
    corrections.write_text(
        json.dumps(
            {
                "reviewer": "بازبین",
                "items": [
                    {
                        "segment_id": 1,
                        "decision": "candidate",
                        "candidate_index": 1,
                    }
                ],
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    report = apply_accuracy_review(job, corrections)
    assert report["status"] == "accuracy_human_resolved"


def test_evaluate_corpus_reports_micro_averaged_metrics(tmp_path: Path) -> None:
    corpus = tmp_path / "corpus.jsonl"
    corpus.write_text(
        "\n".join(
            [
                json.dumps(
                    {"id": "clean", "reference": "این متن درست است", "hypothesis": "این متن درست است"},
                    ensure_ascii=False,
                ),
                json.dumps(
                    {"id": "error", "reference": "نام علی است", "hypothesis": "نام رضا است"},
                    ensure_ascii=False,
                ),
            ]
        ),
        encoding="utf-8",
    )
    report = evaluate_corpus(corpus)
    assert report["sample_count"] == 2
    assert report["reference_words"] == 7
    assert report["word_errors"] == 1
    assert report["wer"] == round(1 / 7, 6)


def test_evaluate_corpus_rejects_incomplete_rows(tmp_path: Path) -> None:
    corpus = tmp_path / "corpus.jsonl"
    corpus.write_text('{"id": "missing-hypothesis", "reference": "متن"}\n', encoding="utf-8")
    try:
        evaluate_corpus(corpus)
    except Exception as exc:
        assert "hypothesis" in str(exc)
    else:
        raise AssertionError("incomplete corpus row was accepted")
