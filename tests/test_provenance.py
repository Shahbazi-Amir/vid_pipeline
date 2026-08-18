from __future__ import annotations

import json
from pathlib import Path

from vid_pipeline.provenance import annotate_delivery, record_and_annotate, resolve_provenance


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def test_resolve_separates_original_and_archive_urls() -> None:
    metadata = {
        "source_url": "https://github.com/o/r/releases/download/v1/file.mp3",
        "provenance": {"original_download_url": "https://cdn.example.org/file.mp3"},
    }
    result = resolve_provenance(metadata)
    assert result["original_download_url"] == "https://cdn.example.org/file.mp3"
    assert result["archive_url"].endswith("/file.mp3")


def test_record_and_annotate_adds_original_download_to_all_delivery_files(tmp_path: Path) -> None:
    _write(tmp_path / "source.json", json.dumps({"schema_version": 2, "title": "نمونه"}))
    _write(tmp_path / "delivery/transcript.md", "# نمونه\n\nمتن\n")
    _write(tmp_path / "delivery/transcript.timestamped.md", "# نمونه\n\n[00:00:00 → 00:00:01]\n\nمتن\n")
    _write(tmp_path / "delivery/transcript.txt", "متن\n")

    result = record_and_annotate(
        tmp_path,
        original_download_url="https://cdn.example.org/original.mp3",
        source_page_url="https://example.org/episode",
        archive_url="https://github.com/o/r/releases/download/v1/file.mp3",
    )
    assert result["original_download_url"].endswith("original.mp3")
    for name in ("transcript.md", "transcript.timestamped.md", "transcript.txt"):
        text = (tmp_path / "delivery" / name).read_text(encoding="utf-8")
        assert "https://cdn.example.org/original.mp3" in text
        assert "https://github.com/o/r/releases/download/v1/file.mp3" in text

    source = json.loads((tmp_path / "source.json").read_text(encoding="utf-8"))
    assert source["provenance"]["original_download_url"].endswith("original.mp3")


def test_annotation_is_idempotent(tmp_path: Path) -> None:
    _write(
        tmp_path / "source.json",
        json.dumps({"original_download_url": "https://cdn.example.org/original.mp3"}),
    )
    _write(tmp_path / "delivery/transcript.md", "# متن\n")
    _write(tmp_path / "delivery/transcript.timestamped.md", "# متن\n")
    _write(tmp_path / "delivery/transcript.txt", "متن\n")
    annotate_delivery(tmp_path)
    first = (tmp_path / "delivery/transcript.txt").read_text(encoding="utf-8")
    annotate_delivery(tmp_path)
    second = (tmp_path / "delivery/transcript.txt").read_text(encoding="utf-8")
    assert first == second
