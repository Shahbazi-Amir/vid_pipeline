from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from vid_pipeline.editorial import (
    EditorialConfig,
    EditorialMetadata,
    build_editorial_chunks,
    edit_transcript,
    markdown_to_text,
)


class FakeClient:
    def __init__(self) -> None:
        self.calls = 0

    def edit(self, *, instructions: str, input_text: str) -> str:
        self.calls += 1
        self.last_instructions = instructions
        self.last_input = input_text
        return f"## بخش {self.calls}\n\n**گوینده:** متن ویرایش‌شدۀ بخش {self.calls}."


class EditorialTests(unittest.TestCase):
    def test_chunks_preserve_segment_order(self) -> None:
        segments = [
            {"id": index, "start": index, "end": index + 1, "text": "واژه " * 300}
            for index in range(3)
        ]
        chunks = build_editorial_chunks(segments, max_chars=2000)
        joined = "\n".join(chunks)
        self.assertLess(joined.index("S0000"), joined.index("S0001"))
        self.assertLess(joined.index("S0001"), joined.index("S0002"))

    def test_edit_transcript_writes_reviewed_formats(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            raw = root / "raw.json"
            raw.write_text(
                json.dumps(
                    {
                        "language": "fa",
                        "segments": [
                            {"id": 0, "start": 0, "end": 2, "text": "سلام این متن خام است"},
                            {"id": 1, "start": 2, "end": 4, "text": "ادامه گفتگو"},
                        ],
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
            md = root / "final.md"
            txt = root / "final.txt"
            fake = FakeClient()
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
            self.assertEqual(result["status"], "ai_editorial_completed")
            self.assertIn("# عنوان نمونه", md.read_text(encoding="utf-8"))
            self.assertIn("**گوینده:**", md.read_text(encoding="utf-8"))
            self.assertNotIn("**", txt.read_text(encoding="utf-8"))
            self.assertEqual(fake.calls, 1)

    def test_markdown_to_text_keeps_content(self) -> None:
        value = markdown_to_text("## عنوان\n\n**مجری:** سلام")
        self.assertIn("عنوان", value)
        self.assertIn("مجری: سلام", value)


if __name__ == "__main__":
    unittest.main()
