import importlib.util
import json
from argparse import Namespace
from pathlib import Path


def _module():
    path = Path(__file__).parents[1] / "scripts" / "chunked_transcript.py"
    spec = importlib.util.spec_from_file_location("chunked_transcript", path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_merge_chunks_offsets_segments_and_words(tmp_path) -> None:
    module = _module()
    chunks = tmp_path / "chunks"
    chunks.mkdir()
    template = {
        "language": "fa",
        "model": "large-v3-turbo",
        "segments": [
            {
                "id": 0,
                "start": 1.0,
                "end": 2.0,
                "text": "آزمایش",
                "words": [{"start": 1.0, "end": 2.0, "word": "آزمایش"}],
            }
        ],
    }
    (chunks / "chunk-000.json").write_text(
        json.dumps({**template, "chunk_offset": 0}),
        encoding="utf-8",
    )
    (chunks / "chunk-001.json").write_text(
        json.dumps({**template, "chunk_offset": 600}),
        encoding="utf-8",
    )
    output_json = tmp_path / "raw.json"
    output_markdown = tmp_path / "raw.md"

    module.merge_chunks(
        Namespace(
            input_dir=chunks,
            output_json=output_json,
            output_markdown=output_markdown,
            language="fa",
            chunk_seconds=600,
        )
    )

    result = json.loads(output_json.read_text(encoding="utf-8"))
    assert result["chunk_count"] == 2
    assert [item["id"] for item in result["segments"]] == [0, 1]
    assert result["segments"][1]["start"] == 601.0
    assert result["segments"][1]["words"][0]["start"] == 601.0
    assert "10:01.000" in output_markdown.read_text(encoding="utf-8")
