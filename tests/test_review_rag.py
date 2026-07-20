import json
import tempfile
import unittest
from pathlib import Path

from vid_pipeline.models import EpisodeSpec
from vid_pipeline.rag import build_rag, validate_jsonl
from vid_pipeline.review import create_review_package, mark_reviewed


class ReviewRagTests(unittest.TestCase):
    def spec(self):
        return EpisodeSpec(
            program="عصر شیرین",
            collection="asre-shirin-season-2",
            season="فصل دوم",
            season_episode=1,
            overall_episode=14,
            speaker="دکتر کمیل رودی",
            title="نمونه",
            source_url="https://example.com/page",
            video_url="https://www.aparat.com/v/example",
        )

    def test_review_and_rag(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            raw = root / "raw.json"
            raw.write_text(
                json.dumps(
                    {
                        "segments": [
                            {
                                "start": 0,
                                "end": 5,
                                "text": "متن خام نمونه",
                                "review_flags": [],
                            }
                        ]
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
            review = create_review_package(self.spec(), raw, root / "review.md")
            self.assertIn("متن خام نمونه", review.read_text(encoding="utf-8"))
            audio = root / "audio.wav"
            audio.write_bytes(b"fake audio for checksum")
            final = root / "final.md"
            final.write_text(
                "# نمونه\n\n## بخش اول\n\n" + ("این متن بازبینی شده است. " * 20),
                encoding="utf-8",
            )
            receipt = mark_reviewed(audio, final, root / "receipt.json", "tester", True)
            output = root / "rag.jsonl"
            records = build_rag(self.spec(), final, receipt, output)
            self.assertGreaterEqual(len(records), 1)
            self.assertEqual(validate_jsonl(output), len(records))


class ReviewIntegrityTests(unittest.TestCase):
    def test_modified_transcript_requires_new_review(self):
        from vid_pipeline.errors import ReviewRequiredError
        from vid_pipeline.review import verify_review

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            audio = root / "audio.wav"
            audio.write_bytes(b"audio")
            final = root / "final.md"
            final.write_text(
                "# عنوان\n\n## بخش\n\n" + ("متن بررسی شده. " * 20), encoding="utf-8"
            )
            receipt = mark_reviewed(audio, final, root / "receipt.json", "tester", True)
            final.write_text(final.read_text(encoding="utf-8") + "تغییر", encoding="utf-8")
            with self.assertRaises(ReviewRequiredError):
                verify_review(final, receipt)


if __name__ == "__main__":
    unittest.main()
