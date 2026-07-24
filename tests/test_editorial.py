from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from vid_pipeline.editorial import (
    EditorialConfig,
    EditorialMetadata,
    assess_transcript_preservation,
    build_editorial_chunks,
    edit_transcript,
    enforce_readable_paragraphs,
    markdown_to_text,
)


class PreservingClient:
    def __init__(self) -> None:
        self.calls = 0

    def edit(self, *, instructions: str, input_text: str) -> str:
        self.calls += 1
        raw = input_text.split("متن خام:\n", 1)[1]
        lines: list[str] = []
        for line in raw.splitlines():
            _, _, text = line.partition("] ")
            lines.append(text or line)
        return " ".join(lines)


class TruncatingClient:
    def edit(self, *, instructions: str, input_text: str) -> str:
        return "بسم الله الرحمن الرحیم"


class FailingClient:
    def edit(self, *, instructions: str, input_text: str) -> str:
        raise OSError("editorial timeout")


class EditorialTests(unittest.TestCase):
    def _long_raw(self, root: Path, count: int = 80) -> Path:
        raw = root / "raw.json"
        raw.write_text(
            json.dumps(
                {
                    "language": "fa",
                    "segments": [
                        {
                            "id": index,
                            "start": index * 2,
                            "end": index * 2 + 2,
                            "text": (
                                f"این جمله شماره {index} برای آزمایش حفظ کامل متن است "
                                "و نباید از خروجی حذف شود."
                            ),
                        }
                        for index in range(count)
                    ],
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
        return raw

    def test_chunks_preserve_segment_order(self) -> None:
        segments = [
            {"id": index, "start": index, "end": index + 1, "text": "واژه " * 300}
            for index in range(3)
        ]
        chunks = build_editorial_chunks(segments, max_chars=2000)
        joined = "\n".join(chunks)
        self.assertLess(joined.index("S0000"), joined.index("S0001"))
        self.assertLess(joined.index("S0001"), joined.index("S0002"))

    def test_enforce_readable_paragraphs_splits_long_model_output(self) -> None:
        value = enforce_readable_paragraphs(
            "**گوینده:** جملۀ اول. جملۀ دوم. جملۀ سوم. جملۀ چهارم."
        )
        paragraphs = value.split("\n\n")
        self.assertEqual(len(paragraphs), 2)
        self.assertIn("جملۀ دوم.", paragraphs[0])
        self.assertIn("جملۀ سوم.", paragraphs[1])

    def test_edit_transcript_writes_reviewed_formats(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            raw = root / "raw.json"
            raw.write_text(
                json.dumps(
                    {
                        "language": "fa",
                        "segments": [
                            {
                                "id": 0,
                                "start": 0,
                                "end": 2,
                                "text": "جملۀ اول. جملۀ دوم.",
                            },
                            {
                                "id": 1,
                                "start": 2,
                                "end": 4,
                                "text": "جملۀ سوم. جملۀ چهارم.",
                            },
                        ],
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
            md = root / "final.md"
            txt = root / "final.txt"
            fake = PreservingClient()
            result = edit_transcript(
                raw,
                md,
                txt,
                metadata=EditorialMetadata(
                    title="عنوان نمونه",
                    program="برنامۀ نمونه",
                    guest="مهمان نمونه",
                    source_url="https://example.com/video",
                ),
                config=EditorialConfig(chunk_chars=2000),
                client=fake,
            )
            self.assertEqual(result["status"], "local_editorial_completed")
            self.assertFalse(result["fallback_used"])
            markdown = md.read_text(encoding="utf-8")
            self.assertIn("# عنوان نمونه", markdown)
            self.assertIn("جملۀ دوم.\n\nجملۀ سوم.", markdown)
            self.assertNotIn("**", txt.read_text(encoding="utf-8"))
            self.assertEqual(fake.calls, 1)

    def test_truncated_chunk_falls_back_to_complete_source(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            raw = self._long_raw(root)
            result = edit_transcript(
                raw,
                root / "final.md",
                root / "final.txt",
                config=EditorialConfig(chunk_chars=2000, second_pass=False),
                client=TruncatingClient(),
            )
            final_text = (root / "final.txt").read_text(encoding="utf-8")
            self.assertEqual(result["status"], "local_editorial_completed_with_fallback")
            self.assertTrue(result["fallback_used"])
            self.assertTrue(result["fallback_chunks"])
            self.assertTrue(result["final_validation"]["accepted"])
            self.assertIn("شماره 0", final_text)
            self.assertIn("شماره 79", final_text)

    def test_editorial_error_falls_back_without_losing_text(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            raw = self._long_raw(root)
            result = edit_transcript(
                raw,
                root / "final.md",
                root / "final.txt",
                config=EditorialConfig(chunk_chars=2000, second_pass=False),
                client=FailingClient(),
            )
            final_text = (root / "final.txt").read_text(encoding="utf-8")
            self.assertTrue(result["fallback_used"])
            self.assertIn("شماره 79", final_text)

    def test_preservation_metric_rejects_catastrophic_truncation(self) -> None:
        result = assess_transcript_preservation(
            "یک دو سه چهار پنج شش هفت هشت نه ده",
            "یک دو",
        )
        self.assertFalse(result["accepted"])
        self.assertIn("candidate_too_short", result["reasons"])

    def test_markdown_to_text_keeps_content(self) -> None:
        value = markdown_to_text("## عنوان\n\n**مجری:** سلام")
        self.assertIn("عنوان", value)
        self.assertIn("مجری: سلام", value)


if __name__ == "__main__":
    unittest.main()
