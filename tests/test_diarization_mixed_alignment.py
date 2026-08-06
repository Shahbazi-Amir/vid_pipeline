from vid_pipeline.diarization import SpeakerTurn, align_segments


def test_word_row_after_stale_text_row_does_not_require_speaker_evidence():
    turns = [SpeakerTurn(0.0, 2.0, "SPEAKER_00")]
    segments = [
        {
            "start": 0.0,
            "end": 1.0,
            "text": "متن اصلاح‌شده",
            "words": [
                {"start": 0.0, "end": 0.4, "word": " متن"},
                {"start": 0.4, "end": 0.8, "word": " قدیمی"},
            ],
        },
        {
            "start": 1.0,
            "end": 1.4,
            "text": "ادامه",
            "words": [{"start": 1.0, "end": 1.4, "word": " ادامه"}],
        },
    ]

    aligned, ambiguous = align_segments(segments, turns)

    assert ambiguous == 0
    assert len(aligned) == 2
    assert aligned[0]["text"] == "متن اصلاح‌شده"
    assert "speaker_evidence" not in aligned[0]
    assert aligned[1]["text"] == "ادامه"
    assert aligned[1]["speaker"] == "SPEAKER_00"
    assert aligned[1]["speaker_evidence"]["speaker"] == "SPEAKER_00"
