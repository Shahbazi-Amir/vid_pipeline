from __future__ import annotations

import json
from argparse import Namespace
from pathlib import Path
from unittest.mock import patch

import pytest

from vid_pipeline.chunking import plan_chunks, validate_chunk_plans
from vid_pipeline.cli import command_run_folder
from vid_pipeline.merge import merge_chunk_segments
from vid_pipeline.models import JobRequest, TranscriptDocument, TranscriptSegment
from vid_pipeline.render import render_outputs
from vid_pipeline.review_provider import NoOpReviewProvider, ReviewContext
from vid_pipeline.storage import LocalArtifactStore


def test_chunk_plan_overlap_and_no_overlap() -> None:
    plans = plan_chunks(1201, chunk_duration=600, overlap=15, source_hash="abc")
    validate_chunk_plans(plans)
    assert [(item.start, item.end) for item in plans] == [
        (0.0, 615.0),
        (585.0, 1215.0 if False else 1201),
        (1185.0, 1201),
    ]
    assert plan_chunks(601, chunk_duration=600, overlap=0)[1].start == 600


def test_invalid_chunk_plans() -> None:
    plans = plan_chunks(1200)
    with pytest.raises(ValueError, match="continuous"):
        validate_chunk_plans([plans[1]])


def test_merge_boundary_deduplicates_but_keeps_similar_sentence() -> None:
    chunks = [
        {
            "chunk_index": 0,
            "start": 0,
            "segments": [{"start": 590, "end": 600, "text": "امروز درباره اقتصاد ایران صحبت می کنیم"}],
        },
        {
            "chunk_index": 1,
            "start": 585,
            "segments": [
                {
                    "start": 5,
                    "end": 18,
                    "text": "درباره اقتصاد ایران صحبت می کنیم و سپس نتیجه را می گوییم",
                },
                {"start": 30, "end": 40, "text": "امروز درباره اقتصاد ایران صحبت می کنیم"},
            ],
        },
    ]
    merged = merge_chunk_segments(chunks)
    assert "و سپس نتیجه" in merged[1]["text"]
    assert len(merged) == 3


def test_merge_rejects_missing_duplicate_and_bad_timestamp() -> None:
    with pytest.raises(ValueError, match="continuous"):
        merge_chunk_segments([{"chunk_index": 1, "start": 0, "segments": []}])
    with pytest.raises(ValueError, match="timestamps"):
        merge_chunk_segments(
            [{"chunk_index": 0, "start": 0, "segments": [{"start": -1, "end": 1, "text": "x"}]}]
        )


def test_job_request_serialization() -> None:
    request = JobRequest("job", "file", "/input.wav")
    assert JobRequest.from_dict(request.to_dict()) == request


def test_storage_adapter_blocks_escape(tmp_path: Path) -> None:
    source = tmp_path / "source.txt"
    source.write_text("ok", encoding="utf-8")
    store = LocalArtifactStore(tmp_path / "artifacts")
    destination = store.save(source, "job/final.txt")
    assert Path(destination).read_text(encoding="utf-8") == "ok"
    with pytest.raises(ValueError):
        store.exists("../escape")


def test_render_all_formats_and_noop_review(tmp_path: Path) -> None:
    document = TranscriptDocument(
        job_id="job",
        language="fa",
        segments=[TranscriptSegment(0, 0, 1.5, "سلام دنیا", confidence=0.9)],
    )
    result = NoOpReviewProvider().review(document, ReviewContext())
    assert result.provider == "noop"
    paths = render_outputs(result.document, tmp_path)
    assert set(paths) == {"json", "timecoded_markdown", "srt", "vtt", "markdown", "text"}
    payload = json.loads(Path(paths["json"]).read_text(encoding="utf-8"))
    assert payload["segments"][0]["review_status"] == "machine_transcribed"
    assert "-->" in Path(paths["srt"]).read_text(encoding="utf-8")


def test_run_folder_is_recursive_and_isolates_failures(tmp_path: Path, capsys) -> None:
    media = tmp_path / "media"
    nested = media / "nested"
    nested.mkdir(parents=True)
    (media / "good.mp4").write_bytes(b"good")
    (nested / "bad.wav").write_bytes(b"bad")
    args = Namespace(
        path=media,
        recursive=True,
        output_root=tmp_path / "outputs",
        workers=1,
        extensions="",
        force=False,
        resume=True,
        profile="balanced",
        model="small",
        language="fa",
        editorial_model="unused",
        no_editorial=True,
    )

    def fake_run_file(namespace: Namespace) -> int:
        if namespace.path.name == "bad.wav":
            raise RuntimeError("broken media")
        return 0

    with patch("vid_pipeline.cli.command_run_file", side_effect=fake_run_file):
        assert command_run_folder(args) == 1
    output = capsys.readouterr().out
    summary = json.loads(output)
    assert summary["total"] == 2
    assert summary["successful"] == 1
    assert summary["failed"] == 1
