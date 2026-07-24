from __future__ import annotations

import json
import tempfile
import unittest
from unittest.mock import patch

from vid_pipeline.editorial import EditorialConfig
from vid_pipeline.standalone import VideoPipeline


class StandaloneEditorialFallbackTests(unittest.TestCase):
    def test_pipeline_publishes_complete_machine_fallback_on_editorial_failure(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            pipeline = VideoPipeline(
                "https://example.com/audio.mp3",
                directory,
                "fallback-test",
            )
            segments = [
                {
                    "id": index,
                    "start": index,
                    "end": index + 1,
                    "text": (
                        f"این جمله شماره {index} است و باید در خروجی کامل باقی بماند."
                    ),
                }
                for index in range(100)
            ]
            pipeline.paths.raw_json.write_text(
                json.dumps(
                    {"language": "fa", "segments": segments},
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
            complete_text = " ".join(segment["text"] for segment in segments)
            pipeline.paths.machine_text.write_text(complete_text, encoding="utf-8")
            pipeline.paths.machine_markdown.write_text(
                f"# متن ماشینی\n\n{complete_text}\n",
                encoding="utf-8",
            )

            with patch(
                "vid_pipeline.standalone.edit_transcript",
                side_effect=OSError("editorial timeout"),
            ):
                details = pipeline.editorial(EditorialConfig(), force=True)

            final_text = pipeline.paths.final_text.read_text(encoding="utf-8")
            result = json.loads(pipeline.paths.result.read_text(encoding="utf-8"))
            self.assertEqual(details["status"], "machine_fallback")
            self.assertEqual(result["status"], "completed_with_fallback")
            self.assertEqual(result["review_status"], "machine_fallback")
            self.assertTrue(result["content_preservation"]["accepted"])
            self.assertIn("شماره 0", final_text)
            self.assertIn("شماره 99", final_text)

    def test_result_uses_fallback_validation_after_invalid_editorial_output(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            pipeline = VideoPipeline(
                "https://example.com/audio.mp3",
                directory,
                "invalid-output-test",
            )
            segments = [
                {
                    "id": index,
                    "start": index,
                    "end": index + 1,
                    "text": f"این جمله شماره {index} باید کامل بماند.",
                }
                for index in range(40)
            ]
            pipeline.paths.raw_json.write_text(
                json.dumps(
                    {"language": "fa", "segments": segments},
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
            complete_text = " ".join(segment["text"] for segment in segments)
            pipeline.paths.machine_text.write_text(complete_text, encoding="utf-8")
            pipeline.paths.machine_markdown.write_text(
                f"# متن ماشینی\n\n{complete_text}\n",
                encoding="utf-8",
            )

            def write_invalid_editorial(*args, **kwargs):
                pipeline.paths.final_text.write_text(
                    ("متن اضافه و نامرتبط " * 500).strip(),
                    encoding="utf-8",
                )
                pipeline.paths.final_markdown.write_text(
                    "# خروجی خراب\n",
                    encoding="utf-8",
                )
                return {
                    "status": "local_editorial_completed",
                    "fallback_used": False,
                }

            with patch(
                "vid_pipeline.standalone.edit_transcript",
                side_effect=write_invalid_editorial,
            ):
                details = pipeline.editorial(EditorialConfig(), force=True)

            result = json.loads(pipeline.paths.result.read_text(encoding="utf-8"))
            final_text = pipeline.paths.final_text.read_text(encoding="utf-8")
            self.assertEqual(details["status"], "machine_fallback")
            self.assertTrue(result["content_preservation"]["accepted"])
            self.assertEqual(result["content_preservation"]["length_ratio"], 1.0)
            self.assertEqual(final_text, complete_text)


if __name__ == "__main__":
    unittest.main()
