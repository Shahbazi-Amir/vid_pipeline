from pathlib import Path

from vid_pipeline.diarization import (
    DiarizationConfig,
    SpeakerTurn,
    align_segments,
    map_roles,
    normalize_turns,
    run_diarization,
)
from vid_pipeline.final_export import export_final_outputs


class FakeBackend:
    name = "fake"

    def diarize(self, audio: Path, *, num_speakers: int | None):
        assert num_speakers == 2
        return [SpeakerTurn(0, 1, "alice"), SpeakerTurn(1, 2, "bob")]


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
