from __future__ import annotations

import pytest

from vid_pipeline.role_mapping import map_roles_with_diagnostics


def _row(speaker: str, start: float, duration: float, text: str) -> dict[str, object]:
    return {
        "speaker": speaker,
        "start": start,
        "end": start + duration,
        "text": text,
        "aligned_word_count": len(text.split()),
    }


def test_clear_interview_pattern_maps_host_and_teacher():
    rows = [
        _row("SPEAKER_00", 0, 3, "آیا این موضوع روشن است؟"),
        _row("SPEAKER_00", 20, 4, "چطور باید شروع کنیم؟"),
        _row("SPEAKER_00", 50, 3, "چه نکته ای مهم است؟"),
        _row("SPEAKER_00", 80, 4, "پس قدم بعدی چیست؟"),
        _row("SPEAKER_01", 4, 16, " ".join(["توضیح"] * 48)),
        _row("SPEAKER_01", 24, 26, " ".join(["پاسخ"] * 75)),
        _row("SPEAKER_01", 53, 27, " ".join(["شرح"] * 82)),
        _row("SPEAKER_01", 84, 30, " ".join(["تحلیل"] * 90)),
    ]
    mapping, diagnostics = map_roles_with_diagnostics(rows, "host-teacher")
    assert mapping["SPEAKER_00"]["role"] == "مجری"
    assert mapping["SPEAKER_01"]["role"] == "استاد"
    assert diagnostics["status"] == "resolved_heuristic"
    assert diagnostics["confidence"] >= 0.72


def test_ambiguous_conversation_stays_unresolved():
    rows = [
        _row("SPEAKER_00", 0, 10, "یک گفتگوی عادی با چند واژه مشابه"),
        _row("SPEAKER_01", 10, 10, "یک گفتگوی عادی با چند واژه مشابه"),
        _row("SPEAKER_00", 20, 10, "ادامه گفتگو بدون الگوی نقش مشخص"),
        _row("SPEAKER_01", 30, 10, "ادامه گفتگو بدون الگوی نقش مشخص"),
    ]
    mapping, diagnostics = map_roles_with_diagnostics(rows, "host-teacher")
    assert not mapping["SPEAKER_00"]["role"]
    assert not mapping["SPEAKER_01"]["role"]
    assert diagnostics["status"] == "unresolved_low_confidence"


def test_manual_override_wins_and_completes_pair():
    rows = [
        _row("SPEAKER_00", 0, 30, " ".join(["شرح"] * 80)),
        _row("SPEAKER_01", 30, 3, "آیا درست است؟"),
    ]
    mapping, diagnostics = map_roles_with_diagnostics(
        rows,
        "host-teacher",
        {"SPEAKER_00": "host"},
    )
    assert mapping["SPEAKER_00"] == {
        "role": "مجری",
        "confidence": 1.0,
        "source": "manual",
    }
    assert mapping["SPEAKER_01"]["role"] == "استاد"
    assert mapping["SPEAKER_01"]["source"] == "manual-complement"
    assert diagnostics["status"] == "resolved_manual"


def test_yani_is_not_treated_as_question_signal():
    rows = [
        _row("SPEAKER_00", 0, 4, "چطور این کار را انجام بدهیم؟"),
        _row("SPEAKER_00", 40, 4, "آیا نکته دیگری هست؟"),
        _row("SPEAKER_01", 4, 36, " ".join(["یعنی"] + ["توضیح"] * 80)),
        _row("SPEAKER_01", 44, 40, " ".join(["یعنی"] + ["شرح"] * 90)),
    ]
    mapping, diagnostics = map_roles_with_diagnostics(rows, "host-teacher")
    assert mapping["SPEAKER_00"]["role"] == "مجری"
    assert mapping["SPEAKER_01"]["role"] == "استاد"
    assert diagnostics["features"]["SPEAKER_01"]["question_count"] == 0


@pytest.mark.parametrize("speaker_count", [1, 3])
def test_auto_mapping_requires_exactly_two_speakers(speaker_count: int):
    rows = [
        _row(f"SPEAKER_{index:02d}", index * 10, 5, "متن نمونه")
        for index in range(speaker_count)
    ]
    mapping, diagnostics = map_roles_with_diagnostics(rows, "host-teacher")
    assert all(not item["role"] for item in mapping.values())
    assert diagnostics["status"] == "unresolved_speaker_count"
