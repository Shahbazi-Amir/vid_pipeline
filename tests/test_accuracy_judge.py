from __future__ import annotations

import json
from pathlib import Path

from vid_pipeline.accuracy_judge import advise_disagreements


def test_judge_cannot_rewrite_or_apply_text(tmp_path: Path) -> None:
    job = tmp_path / "job"
    directory = job / "accuracy"
    directory.mkdir(parents=True)
    (directory / "transcript.consensus.json").write_text(
        json.dumps(
            {
                "segments": [
                    {"id": 0, "text": "قبل"},
                    {"id": 1, "text": "متن اصلی"},
                    {"id": 2, "text": "بعد"},
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
                        "candidates": [
                            {"text": "گزینه اول"},
                            {"text": "گزینه دوم"},
                        ],
                    }
                ]
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    def transport(url: str, payload: bytes, timeout: int) -> dict:
        return {
            "message": {
                "content": json.dumps(
                    {"choice": 1, "uncertain": False},
                    ensure_ascii=False,
                )
            }
        }

    report = advise_disagreements(
        job,
        model="qwen-test",
        transport=transport,
    )
    assert report["judged"] == 1
    disagreements = json.loads(
        (directory / "disagreements.json").read_text(encoding="utf-8")
    )
    advisory = disagreements["items"][0]["llm_advisory"]
    assert advisory["choice"] == 1
    assert advisory["advisory_only"] is True
    assert advisory["applied_to_text"] is False
    consensus = json.loads(
        (directory / "transcript.consensus.json").read_text(encoding="utf-8")
    )
    assert consensus["segments"][1]["text"] == "متن اصلی"
