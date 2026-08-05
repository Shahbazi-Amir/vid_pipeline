from pathlib import Path

import pytest

from vid_pipeline.diarization import (
    DiarizationConfig,
    DiarizationError,
    SpeakerTurn,
    align_segments,
    compare_diarization_runs,
    join_word_tokens,
    map_roles,
    normalize_turns,
    run_diarization,
    select_diarization_consensus,
    smooth_speaker_turns,
)
from vid_pipeline.final_export import export_final_outputs


def _aligned_turn(start, end, speaker, text, *, margin, ambiguous=False):
    return {
        "start": start, "end": end, "speaker": speaker, "text": text,
        "aligned_word_count": len(text.split()),
        "speaker_evidence": {
            "winning_overlap": end - start, "runner_up_overlap": 0.0,
            "overlap_margin": margin, "ambiguous": ambiguous,
            "supporting_raw_turn_duration": end - start,
        },
    }


def test_smoothing_merges_weak_fragmentation_and_preserves_persian_text():
    rows = [
        _aligned_turn(0, 5, "SPEAKER_00", "ساختاری از دانش نگرش و مهارت که ظاهراً", margin=1),
        _aligned_turn(5, 5.8, "SPEAKER_01", "قراره بهش", margin=0, ambiguous=True),
        _aligned_turn(5.8, 10, "SPEAKER_00", "بگیم سواد مالی، می\u200cشود.", margin=1),
    ]
    result, diagnostics = smooth_speaker_turns(rows, DiarizationConfig())
    assert [(row["speaker"], row["text"]) for row in result] == [(
        "SPEAKER_00",
        "ساختاری از دانش نگرش و مهارت که ظاهراً قراره بهش بگیم سواد مالی، می\u200cشود.",
    )]
    assert diagnostics["micro_turns_merged"] == 1
    assert diagnostics["speaker_switches_before"] == 2
    assert diagnostics["speaker_switches_after"] == 0


@pytest.mark.parametrize("reply", ["بله", "نه", "درسته", "دقیقاً", "خب", "آره"])
def test_smoothing_preserves_strong_short_reply(reply):
    rows = [
        _aligned_turn(0, 5, "SPEAKER_00", "آیا این موضوع روشن است؟", margin=1),
        _aligned_turn(5, 5.7, "SPEAKER_01", reply, margin=1),
        _aligned_turn(5.7, 10, "SPEAKER_00", "پس ادامه می\u200cدهیم", margin=1),
    ]
    result, diagnostics = smooth_speaker_turns(rows, DiarizationConfig())
    assert [row["speaker"] for row in result] == ["SPEAKER_00", "SPEAKER_01", "SPEAKER_00"]
    assert diagnostics["micro_turns_preserved"] == 1


def test_smoothing_merges_strong_fragmentary_micro_island_from_live_shape():
    rows = [
        _aligned_turn(0.0, 5.48, "SPEAKER_00", "ساختاری از دانش نگرش و مهارت که ظاهرا", margin=1.0),
        _aligned_turn(5.48, 6.08, "SPEAKER_01", "قراره بهش", margin=0.937),
        _aligned_turn(6.08, 7.54, "SPEAKER_00", "بگیم سواد مالی", margin=1.0),
    ]
    rows[1]["speaker_evidence"]["supporting_raw_turn_duration"] = 0.759
    before_words = sum(int(row["aligned_word_count"]) for row in rows)
    result, diagnostics = smooth_speaker_turns(rows, DiarizationConfig())
    assert len(result) == 1
    assert result[0]["speaker"] == "SPEAKER_00"
    assert result[0]["text"] == (
        "ساختاری از دانش نگرش و مهارت که ظاهرا قراره بهش بگیم سواد مالی"
    )
    assert int(result[0]["aligned_word_count"]) == before_words
    assert diagnostics["strong_micro_islands_merged"] == 1
    assert diagnostics["weak_micro_turns_merged"] == 0
    assert diagnostics["speaker_switches_after"] == 0


def test_smoothing_preserves_protected_backchannel_without_question_boundary():
    rows = [
        _aligned_turn(0, 5, "SPEAKER_00", "این نکته خیلی مهم است", margin=1),
        _aligned_turn(5, 5.6, "SPEAKER_01", "دقیقاً", margin=0.95),
        _aligned_turn(5.6, 10, "SPEAKER_00", "و باید ادامه بدهیم", margin=1),
    ]
    result, diagnostics = smooth_speaker_turns(rows, DiarizationConfig())
    assert [row["speaker"] for row in result] == ["SPEAKER_00", "SPEAKER_01", "SPEAKER_00"]
    assert diagnostics["protected_short_replies_preserved"] == 1


def test_smoothing_does_not_merge_short_text_with_long_raw_support():
    rows = [
        _aligned_turn(0, 5, "SPEAKER_00", "شروع جمله", margin=1),
        _aligned_turn(5, 5.6, "SPEAKER_01", "دو کلمه", margin=0.95),
        _aligned_turn(5.6, 10, "SPEAKER_00", "ادامه جمله", margin=1),
    ]
    rows[1]["speaker_evidence"]["supporting_raw_turn_duration"] = 1.8
    result, diagnostics = smooth_speaker_turns(rows, DiarizationConfig())
    assert len(result) == 3
    assert diagnostics["strong_micro_islands_merged"] == 0


def test_smoothing_merges_near_zero_weak_token_but_not_a_b_c():
    config = DiarizationConfig()
    sandwich = [
        _aligned_turn(0, 5, "SPEAKER_00", "شروع", margin=1),
        _aligned_turn(5, 5.05, "SPEAKER_01", "لغزش؟", margin=0, ambiguous=True),
        _aligned_turn(5.05, 10, "SPEAKER_00", "ادامه", margin=1),
    ]
    assert len(smooth_speaker_turns(sandwich, config)[0]) == 1
    distinct = [dict(row) for row in sandwich]
    distinct[-1]["speaker"] = "SPEAKER_02"
    assert len(smooth_speaker_turns(distinct, config)[0]) == 3


def test_required_gate_rolls_back_smoothing_speaker_collapse(tmp_path: Path):
    class NestedWeakBackend:
        name = "fake"

        def diarize(self, audio: Path, *, num_speakers: int | None):
            return [
                SpeakerTurn(0, 10, "speaker_00"),
                SpeakerTurn(5, 5.8, "speaker_01"),
            ]

    words = [
        {"start": 4, "end": 5, "word": " شروع"},
        {"start": 5, "end": 5.4, "word": " لغزش"},
        {"start": 5.4, "end": 5.8, "word": " کوتاه"},
        {"start": 5.8, "end": 6.8, "word": " ادامه"},
    ]
    output = tmp_path / "diarization.json"
    aligned, _ = run_diarization(
        tmp_path / "audio.wav",
        [{"start": 0, "end": 10, "text": "شروع لغزش کوتاه ادامه", "words": words}],
        DiarizationConfig(
            enabled=True, required=True, num_speakers=2,
            effective_min_duration_seconds=0.5, effective_min_fraction=0.01,
            aligned_min_word_count=1, aligned_min_duration_seconds=0.1,
            aligned_min_fraction=0.01,
        ),
        backend=NestedWeakBackend(), output=output,
    )
    report = __import__("json").loads(output.read_text(encoding="utf-8"))
    assert report["pre_smoothing_segments"] == 3
    assert report["post_smoothing_segments"] == 1
    assert report["micro_turns_merged"] == 1
    assert report["candidate_post_smoothing_effective_speaker_count"] == 1
    assert report["aligned_effective_speaker_count"] == 2
    assert report["smoothing_accepted"] is False
    assert report["smoothing_rollback"] is True
    assert report["smoothing_rollback_reason"] == "speaker_collapse"
    assert [(row["start"], row["end"], row["speaker"], row["text"]) for row in aligned] == [
        (4.0, 5.0, "SPEAKER_00", "شروع"),
        (5.0, 5.8, "SPEAKER_01", "لغزش کوتاه"),
        (5.8, 6.8, "SPEAKER_00", "ادامه"),
    ]


def _healthy_turns(first="speaker_00", second="speaker_01"):
    return [
        SpeakerTurn(0, 410, first),
        SpeakerTurn(410, 935, second),
    ]


def test_reproducibility_comparison_ignores_label_permutation():
    comparison = compare_diarization_runs(
        _healthy_turns(), _healthy_turns("speaker_01", "speaker_00")
    )
    assert comparison["speaker_count_agreement"] is True
    assert comparison["timeline_assignment_agreement"] == pytest.approx(1.0)


def test_reproducibility_detects_severe_duration_collapse():
    pathological = [
        SpeakerTurn(0, 932, "speaker_00"),
        SpeakerTurn(123, 137, "speaker_01"),
    ]
    comparison = compare_diarization_runs(_healthy_turns(), pathological)
    assert comparison["timeline_assignment_agreement"] < 0.9
    assert comparison["minority_fraction_difference"] > 0.4


def test_reproducibility_selects_consensus_and_rejects_all_disagree():
    config = DiarizationConfig()
    healthy = _healthy_turns()
    swapped = _healthy_turns("speaker_01", "speaker_00")
    pathological = [
        SpeakerTurn(0, 932, "speaker_00"),
        SpeakerTurn(123, 137, "speaker_01"),
    ]
    selected, report = select_diarization_consensus([healthy, swapped, pathological], config)
    assert selected in {0, 1}
    assert report["best_pair_agreement"] == pytest.approx(1.0)
    assert report["stable"] is False

    third = [
        SpeakerTurn(0, 100, "speaker_00"),
        SpeakerTurn(100, 935, "speaker_01"),
    ]
    with pytest.raises(DiarizationError, match="severe_disagreement=true"):
        select_diarization_consensus([healthy, pathological, third], config)


def test_pathological_backend_retries_and_keeps_healthy_consensus(tmp_path: Path):
    outputs = [
        [SpeakerTurn(0, 932, "speaker_00"), SpeakerTurn(123, 137, "speaker_01")],
        _healthy_turns(),
        _healthy_turns("speaker_01", "speaker_00"),
    ]

    class Backend:
        name = "fake"

        def __init__(self):
            self.calls = 0

        def diarize(self, audio: Path, *, num_speakers: int | None):
            value = outputs[self.calls]
            self.calls += 1
            return value

    words = [
        {"start": second, "end": second + 1, "word": f" واژه{index}"}
        for index, second in enumerate((1, 2, 3, 500, 501, 502))
    ]
    backend = Backend()
    _, report = run_diarization(
        tmp_path / "audio.wav",
        [{"start": 0, "end": 935, "text": " ".join(w["word"].strip() for w in words),
          "words": words}],
        DiarizationConfig(required=True, num_speakers=2),
        backend=backend,
    )
    assert backend.calls == 3
    assert report["reproducibility"]["selected_attempt"] in {2, 3}
    assert report["raw_effective_speaker_count"] == 2


class FakeBackend:
    name = "fake"

    def diarize(self, audio: Path, *, num_speakers: int | None):
        assert num_speakers == 2
        return [SpeakerTurn(0, 1, "alice"), SpeakerTurn(1, 2, "bob")]


def test_run_diarization_rejects_zero_turns(tmp_path: Path):
    class EmptyBackend:
        name = "empty"

        def diarize(self, audio: Path, *, num_speakers: int | None):
            return []

    with pytest.raises(DiarizationError, match="zero speakers"):
        run_diarization(
            tmp_path / "audio.wav", [], DiarizationConfig(enabled=True), backend=EmptyBackend()
        )


def test_normalization_word_split_and_short_interjection():
    turns = normalize_turns([SpeakerTurn(1, 2, "b"), SpeakerTurn(0, 1, "a")])
    segments = [{"start": 0, "end": 2, "text": "سلام بله", "words": [
        {"start": 0.1, "end": 0.8, "word": "سلام"},
        {"start": 1.1, "end": 1.3, "word": "بله"},
    ]}]
    aligned, ambiguous = align_segments(segments, turns)
    assert [row["speaker"] for row in aligned] == ["SPEAKER_00", "SPEAKER_01"]
    assert [row["text"] for row in aligned] == ["سلام", "بله"]
    assert ambiguous == 0


@pytest.mark.parametrize(("tokens", "expected"), [
    (["سلام", " به", " همه"], "سلام به همه"),
    (["این", " یک", " تست", " است"], "این یک تست است"),
    (["سلام", "،", " دنیا"], "سلام، دنیا"),
    (["آیا", " خوب", " است", "؟"], "آیا خوب است؟"),
    (["می\u200cشود"], "می\u200cشود"),
    (["برنامه\u200cریزی", " و", " سرمایه\u200cگذاری"], "برنامه\u200cریزی و سرمایه\u200cگذاری"),
])
def test_join_word_tokens_preserves_persian_spacing(tokens, expected):
    assert join_word_tokens(tokens) == expected


def test_alignment_preserves_persian_spacing_and_speaker_timeline():
    turns = normalize_turns([
        SpeakerTurn(0, 5, "speaker_00"),
        SpeakerTurn(5, 10, "speaker_01"),
        SpeakerTurn(10, 15, "speaker_00"),
    ])
    segments = [{"start": 0, "end": 15, "text": "سلام به همه بله دوباره", "words": [
        {"start": 1, "end": 2, "word": "سلام"},
        {"start": 2, "end": 3, "word": " به"},
        {"start": 3, "end": 4, "word": " همه"},
        {"start": 6, "end": 7, "word": " بله"},
        {"start": 11, "end": 12, "word": " دوباره"},
    ]}]
    aligned, ambiguous = align_segments(segments, turns)
    assert [row["speaker"] for row in aligned] == [
        "SPEAKER_00", "SPEAKER_01", "SPEAKER_00"
    ]
    assert [row["text"] for row in aligned] == ["سلام به همه", "بله", "دوباره"]
    assert " ".join(row["text"] for row in aligned) == segments[0]["text"]
    assert ambiguous == 0


def test_normalization_never_collapses_distinct_raw_labels():
    turns = normalize_turns([
        SpeakerTurn(0, 1, "speaker_00"), SpeakerTurn(1, 2, "speaker_01")
    ])
    assert [turn.speaker for turn in turns] == ["SPEAKER_00", "SPEAKER_01"]


def test_overlap_is_deterministic_and_three_speakers_are_generic():
    turns = [SpeakerTurn(0, 1, "SPEAKER_00"), SpeakerTurn(0, 1, "SPEAKER_01")]
    aligned, ambiguous = align_segments([{"start": 0, "end": 1, "text": "x"}], turns)
    assert aligned[0]["speaker"] == "SPEAKER_00"
    assert ambiguous == 1
    mapping = map_roles([
        {"speaker": "SPEAKER_00", "text": "چه می‌شود؟"},
        {"speaker": "SPEAKER_01", "text": "پاسخ طولانی"},
        {"speaker": "SPEAKER_02", "text": "سوم"},
    ], "host-teacher")
    assert all(not value["role"] for value in mapping.values())


def test_nested_turn_wins_equal_overlap_by_temporal_specificity():
    turns = [
        SpeakerTurn(0, 100, "SPEAKER_00"),
        SpeakerTurn(20, 22, "SPEAKER_01"),
    ]
    aligned, ambiguous = align_segments([{
        "start": 20, "end": 22, "text": "پاسخ کوتاه",
        "words": [
            {"start": 20.1, "end": 20.8, "word": " پاسخ"},
            {"start": 20.8, "end": 21.5, "word": " کوتاه"},
        ],
    }], turns)
    assert {row["speaker"] for row in aligned} == {"SPEAKER_01"}
    assert ambiguous == 2


def test_changed_consensus_text_is_never_overwritten_by_stale_words():
    aligned, _ = align_segments([{
        "start": 0, "end": 2, "text": "متن بهتر انسانی",
        "words": [{"start": 0, "end": 1, "word": "متن خام"}],
    }], [SpeakerTurn(0, 2, "SPEAKER_00")])
    assert aligned[0]["text"] == "متن بهتر انسانی"


def test_manual_roles_and_fake_backend(tmp_path: Path):
    audio = tmp_path / "audio.wav"
    audio.write_bytes(b"fake")
    segments, report = run_diarization(audio, [{"start": 0, "end": 2, "text": "متن"}], DiarizationConfig(
        enabled=True, num_speakers=2, role_overrides={"SPEAKER_00": "host"}
    ), backend=FakeBackend())
    assert report["detected_speaker_count"] == 2
    assert segments[0]["speaker_role"] == "مجری"


def test_diagnostics_and_required_quality_gate_after_alignment(tmp_path: Path):
    class CollapsedBackend:
        name = "fake"

        def diarize(self, audio: Path, *, num_speakers: int | None):
            assert num_speakers == 2
            return [SpeakerTurn(0, 90, "speaker_00"), SpeakerTurn(90, 100, "speaker_01")]

    output = tmp_path / "diarization.json"
    config = DiarizationConfig(enabled=True, required=True, num_speakers=2)
    with pytest.raises(
        DiarizationError,
        match=r"requested=2 raw_effective=2 aligned_effective=1",
    ):
        run_diarization(
            tmp_path / "audio.wav",
            [{
                "start": 0, "end": 90, "text": "یک متن معنی دار",
                "words": [
                    {"start": 1, "end": 2, "word": " یک"},
                    {"start": 2, "end": 3, "word": " متن"},
                    {"start": 3, "end": 4, "word": " معنی"},
                    {"start": 4, "end": 5, "word": " دار"},
                ],
            }],
            config,
            backend=CollapsedBackend(),
            output=output,
        )
    report = __import__("json").loads(output.read_text(encoding="utf-8"))
    assert report["raw_speakers"] == ["speaker_00", "speaker_01"]
    assert report["normalized_speakers"] == ["SPEAKER_00", "SPEAKER_01"]
    assert report["raw_effective_speaker_count"] == 2
    assert report["aligned_effective_speaker_count"] == 1
    assert report["speakers"]["SPEAKER_01"]["word_overlap_duration"] == 0
    assert report["speakers"]["SPEAKER_01"]["aligned_words"] == 0
    assert report["quality_gate_passed"] is False


def test_optional_mode_records_quality_warning_instead_of_failing(tmp_path: Path):
    class OneBackend:
        name = "fake"

        def diarize(self, audio: Path, *, num_speakers: int | None):
            return [SpeakerTurn(0, 10, "speaker_00")]

    _, report = run_diarization(
        tmp_path / "audio.wav",
        [{"start": 0, "end": 10, "text": "متن"}],
        DiarizationConfig(enabled=True, required=False, num_speakers=2),
        backend=OneBackend(),
    )
    assert report["effective_speaker_count"] == 1
    assert "requested=2 raw_effective=1 aligned_effective=0" in report["quality_warning"]


def test_meaningful_second_speaker_passes_effective_gate(tmp_path: Path):
    class HealthyBackend:
        name = "fake"

        def diarize(self, audio: Path, *, num_speakers: int | None):
            return [SpeakerTurn(0, 400, "speaker_00"), SpeakerTurn(400, 480, "speaker_01")]

    words = [
        {"start": start, "end": start + 1, "word": f" واژه{index}"}
        for index, start in enumerate((1, 3, 5, 401, 403, 405))
    ]
    aligned, report = run_diarization(
        tmp_path / "audio.wav",
        [{
            "start": 0, "end": 480,
            "text": " ".join(word["word"].strip() for word in words),
            "words": words,
        }],
        DiarizationConfig(enabled=True, required=True, num_speakers=2),
        backend=HealthyBackend(),
    )
    assert report["effective_speaker_count"] == 2
    assert report["aligned_effective_speaker_count"] == 2
    assert {row["speaker"] for row in aligned} == {"SPEAKER_00", "SPEAKER_01"}


def test_two_speakers_survive_raw_normalized_aligned_and_export(tmp_path: Path):
    class ThreePeriodBackend:
        name = "fake"

        def diarize(self, audio: Path, *, num_speakers: int | None):
            return [
                SpeakerTurn(0, 5, "speaker_00"),
                SpeakerTurn(5, 10, "speaker_01"),
                SpeakerTurn(10, 15, "speaker_00"),
            ]

    words = [
        {"start": second, "end": second + 0.8, "word": f" واژه{index}"}
        for index, second in enumerate((1, 2, 3, 6, 7, 8, 11, 12, 13))
    ]
    text = " ".join(word["word"].strip() for word in words)
    aligned, report = run_diarization(
        tmp_path / "audio.wav",
        [{"start": 0, "end": 15, "text": text, "words": words}],
        DiarizationConfig(enabled=True, required=True, num_speakers=2),
        backend=ThreePeriodBackend(),
        output=tmp_path / "diarization" / "diarization.json",
    )
    assert len(report["raw_speakers"]) == 2
    assert len(report["normalized_speakers"]) == 2
    assert len({row["speaker"] for row in aligned}) == 2
    assert report["aligned_effective_speaker_count"] == 2

    root = tmp_path
    (root / "final").mkdir()
    (root / "accuracy").mkdir()
    (root / "final/transcript.final.md").write_text(text, encoding="utf-8")
    (root / "final/transcript.final.txt").write_text(text, encoding="utf-8")
    (root / "accuracy/transcript.consensus.json").write_text(
        __import__("json").dumps({"segments": aligned}, ensure_ascii=False),
        encoding="utf-8",
    )
    result = export_final_outputs(root)
    assert result["exported_effective_speaker_count"] == 2
    assert "گوینده ۲" in (root / "delivery/transcript.timestamped.md").read_text(
        encoding="utf-8"
    )


def test_speaker_aware_three_file_export(tmp_path: Path):
    root = tmp_path / "job"
    for directory in ("final", "accuracy"):
        (root / directory).mkdir(parents=True, exist_ok=True)
    (root / "final/transcript.final.md").write_text("fallback", encoding="utf-8")
    (root / "final/transcript.final.txt").write_text("fallback", encoding="utf-8")
    (root / "accuracy/transcript.consensus.json").write_text(
        '{"segments":[{"start":0,"end":1,"text":"سلام","speaker":"SPEAKER_00"},'
        '{"start":1,"end":2,"text":"بله","speaker":"SPEAKER_01"}]}', encoding="utf-8"
    )
    export_final_outputs(root)
    assert {p.name for p in (root / "delivery").iterdir()} == {
        "transcript.md", "transcript.txt", "transcript.timestamped.md"
    }
    assert "گوینده ۱" in (root / "delivery/transcript.txt").read_text(encoding="utf-8")
    assert "گوینده ۲" in (root / "delivery/transcript.timestamped.md").read_text(encoding="utf-8")
