from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from vid_pipeline.clean import clean_transcript, normalize_text, ordered_segment_texts


class CleanTranscriptTests(unittest.TestCase):
    def test_normalize_persian_characters_and_spacing(self) -> None:
        self.assertEqual(normalize_text("  يكي   از  متن ها  ؟  "), "یکی از متن ها؟")

    def test_order_is_preserved_and_only_adjacent_duplicate_is_removed(self) -> None:
        segments = [
            {"text": "بخش اول"},
            {"text": "بخش اول"},
            {"text": "بخش دوم"},
            {"text": "بخش اول"},
        ]
        self.assertEqual(
            ordered_segment_texts(segments),
            ["بخش اول", "بخش دوم", "بخش اول"],
        )

    def test_final_outputs_have_no_timestamps(self) -> None:
        payload = {
            "language": "fa",
            "segments": [
                {"start": 0.0, "end": 2.0, "text": "سلام. "},
                {"start": 2.0, "end": 5.0, "text": "این یک متن آزمایشی است."},
            ],
        }
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            raw = root / "raw.json"
            markdown = root / "final.md"
            text = root / "final.txt"
            raw.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
            result = clean_transcript(
                raw,
                markdown,
                text,
                title="آزمایش",
                source_url="https://example.com/video",
                max_words=20,
            )
            markdown_value = markdown.read_text(encoding="utf-8")
            self.assertNotIn("00:00", markdown_value)
            self.assertNotIn("→", markdown_value)
            self.assertEqual(result["segments_in"], 2)
            self.assertIn("سلام.", text.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
