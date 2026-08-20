from __future__ import annotations

import json
from pathlib import Path

import pytest

from vid_pipeline.review import (
    ReviewConfig,
    ReviewError,
    analyze_segments,
    apply_ai_review,
    apply_human_review,
    audit_transcript_changes,
    build_review_package,
    load_glossaries,
)


def _job(root: Path) -> Path:
    job = root / "job"
    for name in ("raw", "machine", "final", "audio"):
        (job / name).mkdir(parents=True, exist_ok=True)
    raw = {
        "language": "fa",
        "segments": [
            {
                "id": 0,
                "start": 0.0,
                "end": 3.0,
                "text": "شهید رئیزی سخن گفت",
                "avg_logprob": -0.3,
                "no_speech_prob": 0.01,
                "review_flags": [],
                "words": [
                    {"word": "شهید", "start": 0.0, "end": 0.5, "probability": 0.95},
                    {"word": "رئیزی", "start": 0.5, "end": 1.2, "probability": 0.51},
                ],
            },
            {
                "id": 1,
                "start": 3.0,
                "end": 6.0,
                "text": "رشد از صفر به پنج درصد رسید",
                "avg_logprob": -0.2,
                "no_speech_prob": 0.01,
                "review_flags": [],
                "words": [{"word": "پنج", "start": 4.5, "end": 5.0, "probability": 0.90}],
            },
            {
                "id": 2,
                "start": 6.0,
                "end": 9.0,
                "text": "این بخش عادی است",
                "avg_logprob": -0.2,
                "no_speech_prob": 0.01,
                "review_flags": [],
                "words": [{"word": "عادی", "start": 7.0, "end": 7.5, "probability": 0.95}],
            },
        ],
    }
    (job / "raw" / "transcript.raw.json").write_text(
        json.dumps(raw, ensure_ascii=False), encoding="utf-8"
    )
    text = "شهید رئیزی سخن گفت رشد از صفر به پنج درصد رسید این بخش عادی است\n"
    (job / "machine" / "transcript.machine.txt").write_text(text, encoding="utf-8")
    (job / "final" / "transcript.final.txt").write_text(text, encoding="utf-8")
    (job / "audio" / "audio-16k-mono.wav").write_bytes(b"audio-evidence-fixture")
    (job / "result.json").write_text(
        json.dumps({"review_status": "machine_fallback"}), encoding="utf-8"
    )
    return job


def _human_corrections(uncertain: dict, *, reviewer: str = "بازبین انسانی") -> dict:
    return {
        "schema_version": 2,
        "reviewer": reviewer,
        "review_type": "human_audio",
        "verification": {"method": "human_audio", "audio_review_confirmed": True},
        "items": [
            {
                "segment_id": item["segment_id"],
                "decision": "accept_suggestion",
                "replacement": item["proposed_text"],
                "audio_reviewed": True,
            }
            for item in uncertain["items"]
        ],
    }


def test_analyze_segments_flags_confidence_names_numbers_and_glossary(tmp_path: Path) -> None:
    job = _job(tmp_path)
    glossary = tmp_path / "glossary.json"
    glossary.write_text(json.dumps({"رئیسی": ["رئیزی"]}, ensure_ascii=False), encoding="utf-8")
    aliases = load_glossaries([glossary])
    data = json.loads((job / "raw" / "transcript.raw.json").read_text(encoding="utf-8"))
    items = analyze_segments(data, glossary_aliases=aliases)
    assert {item["segment_id"] for item in items} == {0, 1}
    first = items[0]
    assert "low_word_confidence" in first["reasons"]
    assert "person_or_title" in first["reasons"]
    assert "glossary_match" in first["reasons"]
    assert "رئیسی" in first["proposed_text"]
    assert "number_or_percentage" in items[1]["reasons"]


def test_number_detector_does_not_match_inside_words() -> None:
    data = {
        "segments": [
            {
                "id": 7,
                "start": 0.0,
                "end": 1.0,
                "text": "این نیک و درست است",
                "avg_logprob": -0.1,
                "no_speech_prob": 0.0,
                "review_flags": [],
                "words": [{"word": "نیک", "probability": 0.99}],
            }
        ]
    }
    assert analyze_segments(data) == []


def test_audit_detects_large_deletion_and_number_change() -> None:
    audit = audit_transcript_changes(
        "یک دو سه چهار پنج درصد شش هفت هشت نه ده",
        "یک دو سه چهارده",
    )
    assert "large_content_deletion" in audit["warnings"]
    assert "numbers_changed" in audit["warnings"]


def test_build_package_creates_evidence_aware_template(tmp_path: Path) -> None:
    job = _job(tmp_path)
    glossary = tmp_path / "glossary.json"
    glossary.write_text(json.dumps({"رئیسی": ["رئیزی"]}, ensure_ascii=False), encoding="utf-8")
    manifest = build_review_package(
        job,
        config=ReviewConfig(extract_clips=False),
        glossary_paths=[glossary],
    )
    assert manifest["status"] == "human_review_required"
    assert manifest["required_item_count"] == 2
    assert manifest["verification_policy"]["ai_review_can_human_verify"] is False
    template = json.loads((job / "review" / "corrections.template.json").read_text())
    assert template["verification"]["audio_review_confirmed"] is False
    assert all(item["audio_reviewed"] is False for item in template["items"])
    result = json.loads((job / "result.json").read_text(encoding="utf-8"))
    assert result["review_status"] == "human_review_required"
    assert result["human_audio_verification"] is False


def test_package_can_be_built_before_any_final_exists(tmp_path: Path) -> None:
    job = _job(tmp_path)
    (job / "final" / "transcript.final.txt").unlink()
    manifest = build_review_package(job, config=ReviewConfig(extract_clips=False))
    assert manifest["source_files"]["comparison_text"].endswith("transcript.machine.txt")


def test_clean_job_keeps_completed_status_and_marks_review_optional(tmp_path: Path) -> None:
    job = _job(tmp_path)
    raw = {
        "language": "fa",
        "segments": [
            {
                "id": 0,
                "start": 0.0,
                "end": 2.0,
                "text": "متن روشن و عادی است",
                "avg_logprob": -0.1,
                "no_speech_prob": 0.0,
                "review_flags": [],
                "words": [{"word": "روشن", "start": 0.2, "end": 0.8, "probability": 0.98}],
            }
        ],
    }
    (job / "raw" / "transcript.raw.json").write_text(json.dumps(raw, ensure_ascii=False), encoding="utf-8")
    for path in (job / "machine" / "transcript.machine.txt", job / "final" / "transcript.final.txt"):
        path.write_text("متن روشن و عادی است\n", encoding="utf-8")
    (job / "result.json").write_text(
        json.dumps({"status": "completed", "review_status": "ai_editorial_completed"}), encoding="utf-8"
    )
    manifest = build_review_package(job, config=ReviewConfig(extract_clips=False))
    result = json.loads((job / "result.json").read_text(encoding="utf-8"))
    assert manifest["status"] == "human_review_optional"
    assert result["status"] == "completed"
    assert result["review_status"] == "human_review_optional"


def test_human_review_requires_explicit_audio_evidence(tmp_path: Path) -> None:
    job = _job(tmp_path)
    build_review_package(job, config=ReviewConfig(extract_clips=False))
    corrections = job / "review" / "corrections.json"
    corrections.write_text(json.dumps({"reviewer": "بازبین", "items": []}, ensure_ascii=False), encoding="utf-8")
    with pytest.raises(ReviewError, match="explicit"):
        apply_human_review(job, corrections)


def test_human_review_refuses_unreviewed_required_item(tmp_path: Path) -> None:
    job = _job(tmp_path)
    build_review_package(job, config=ReviewConfig(extract_clips=False))
    uncertain = json.loads((job / "review" / "uncertain-spans.json").read_text(encoding="utf-8"))
    corrections = _human_corrections(uncertain)
    corrections["items"][0]["audio_reviewed"] = False
    path = job / "review" / "corrections.json"
    path.write_text(json.dumps(corrections, ensure_ascii=False), encoding="utf-8")
    with pytest.raises(ReviewError, match="audio evidence"):
        apply_human_review(job, path)


def test_chatgpt_cannot_be_marked_human_verified(tmp_path: Path) -> None:
    job = _job(tmp_path)
    build_review_package(job, config=ReviewConfig(extract_clips=False))
    uncertain = json.loads((job / "review" / "uncertain-spans.json").read_text(encoding="utf-8"))
    corrections = _human_corrections(uncertain, reviewer="ChatGPT")
    path = job / "review" / "corrections.json"
    path.write_text(json.dumps(corrections, ensure_ascii=False), encoding="utf-8")
    with pytest.raises(ReviewError, match="cannot produce human_verified"):
        apply_human_review(job, path, promote=True)


def test_ai_review_is_never_human_verified_or_promoted(tmp_path: Path) -> None:
    job = _job(tmp_path)
    build_review_package(job, config=ReviewConfig(extract_clips=False))
    uncertain = json.loads((job / "review" / "uncertain-spans.json").read_text(encoding="utf-8"))
    corrections = {
        "reviewer": "ChatGPT",
        "items": [
            {
                "segment_id": item["segment_id"],
                "decision": "accept_suggestion",
                "replacement": item["proposed_text"],
            }
            for item in uncertain["items"]
        ],
    }
    path = job / "review" / "ai-corrections.json"
    path.write_text(json.dumps(corrections, ensure_ascii=False), encoding="utf-8")
    report = apply_ai_review(job, path, reviewer="ChatGPT")
    assert report["status"] == "ai_reviewed"
    assert report["human_audio_verification"] is False
    assert report["promoted_to_final"] is False
    result = json.loads((job / "result.json").read_text(encoding="utf-8"))
    assert result["review_status"] == "ai_reviewed"
    assert result["human_audio_verification"] is False


def test_human_can_mark_required_segment_unclear_with_audio_evidence(tmp_path: Path) -> None:
    job = _job(tmp_path)
    build_review_package(job, config=ReviewConfig(extract_clips=False))
    uncertain = json.loads((job / "review" / "uncertain-spans.json").read_text(encoding="utf-8"))
    corrections = _human_corrections(uncertain)
    corrections["items"][0].update(decision="unclear", replacement="")
    path = job / "review" / "corrections.json"
    path.write_text(json.dumps(corrections, ensure_ascii=False), encoding="utf-8")
    apply_human_review(job, path, promote=True)
    assert "[نامفهوم]" in (job / "final" / "transcript.final.txt").read_text(encoding="utf-8")


def test_apply_human_review_preserves_all_segments_and_promotes(tmp_path: Path) -> None:
    job = _job(tmp_path)
    glossary = tmp_path / "glossary.json"
    glossary.write_text(json.dumps({"رئیسی": ["رئیزی"]}, ensure_ascii=False), encoding="utf-8")
    build_review_package(job, config=ReviewConfig(extract_clips=False), glossary_paths=[glossary])
    uncertain = json.loads((job / "review" / "uncertain-spans.json").read_text(encoding="utf-8"))
    corrections = _human_corrections(uncertain)
    corrections_path = job / "review" / "corrections.json"
    corrections_path.write_text(json.dumps(corrections, ensure_ascii=False), encoding="utf-8")
    result = apply_human_review(job, corrections_path, promote=True)
    assert result["status"] == "human_verified"
    assert result["verification_method"] == "human_audio"
    assert result["source_audio_sha256"]
    final = (job / "final" / "transcript.final.txt").read_text(encoding="utf-8")
    assert "رئیسی" in final
    assert "پنج درصد" in final
    assert "این بخش عادی است" in final
    published = json.loads((job / "result.json").read_text(encoding="utf-8"))
    assert published["review_status"] == "human_verified"
    assert published["human_audio_verification"] is True
    assert (job / "final" / "human-verification.json").exists()
    assert (job / "final" / "transcript.final.srt").exists()
    assert (job / "final" / "transcript.final.vtt").exists()
    assert "رئیسی" in (job / "delivery" / "transcript.txt").read_text(encoding="utf-8")
    assert "رئیسی" in (job / "delivery" / "transcript.timestamped.md").read_text(encoding="utf-8")
