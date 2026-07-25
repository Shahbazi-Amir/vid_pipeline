from vid_pipeline.review_quality import build_quality_report


def test_quality_score_penalizes_multi_pass_disagreement() -> None:
    report = build_quality_report(
        {
            "segments": [
                {
                    "id": 1,
                    "start": 0,
                    "end": 2,
                    "avg_logprob": -0.2,
                    "no_speech_prob": 0.0,
                    "words": [{"word": "واژه", "probability": 0.95}],
                    "review_flags": [
                        "multi_pass_disagreement",
                        "protected_name_or_number_disagreement",
                    ],
                }
            ]
        }
    )

    assert report["overall_label"] == "low"
    assert report["segments"][0]["review_penalty"] == 0.3

