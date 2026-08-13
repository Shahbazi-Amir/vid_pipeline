from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from vid_pipeline.standalone import VideoJobPaths, VideoPipeline, make_file_job_id, make_job_id


class StandalonePipelineTests(unittest.TestCase):
    def test_job_id_is_stable_and_safe(self) -> None:
        first = make_job_id("https://example.com/watch/video-1")
        second = make_job_id("https://example.com/watch/video-1")
        self.assertEqual(first, second)
        self.assertRegex(first, r"^[a-z0-9._-]+$")

    def test_custom_name_is_used(self) -> None:
        job_id = make_job_id("https://example.com/video", "My Interview")
        self.assertTrue(job_id.startswith("my-interview-"))

    def test_invalid_url_is_rejected(self) -> None:
        with self.assertRaises(ValueError):
            make_job_id("not-a-url")

    def test_output_paths_are_self_contained(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            paths = VideoJobPaths(Path(directory), "sample-12345678")
            paths.ensure()
            self.assertTrue(paths.job_root.exists())
            self.assertEqual(
                paths.machine_markdown,
                Path(directory) / "sample-12345678" / "machine" / "transcript.machine.md",
            )
            self.assertEqual(
                paths.final_markdown,
                Path(directory) / "sample-12345678" / "final" / "transcript.final.md",
            )
            self.assertEqual(
                paths.final_text,
                Path(directory) / "sample-12345678" / "final" / "transcript.final.txt",
            )

    def test_file_job_id_changes_when_content_changes(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            media = Path(directory) / "sample.wav"
            media.write_bytes(b"first")
            first = make_file_job_id(media)
            media.write_bytes(b"other")
            second = make_file_job_id(media)
            self.assertNotEqual(first, second)

    def test_url_provenance_redacts_embedded_credentials(self) -> None:
        url = (
            "https://user:password@example.com/speech.mp3?language=fa"
            "&token=private-value&X-Amz-Signature=secret-signature"
        )
        with tempfile.TemporaryDirectory() as directory:
            pipeline = VideoPipeline(url, directory)
            with patch("vid_pipeline.standalone.extract_metadata", return_value={}):
                pipeline.inspect()
            payload = json.loads(pipeline.paths.source_metadata.read_text(encoding="utf-8"))
        serialized = json.dumps(payload)
        self.assertEqual(payload["source"], "url")
        self.assertIn("language=fa", payload["source_url"])
        self.assertNotIn("password", serialized)
        self.assertNotIn("private-value", serialized)
        self.assertNotIn("secret-signature", serialized)


if __name__ == "__main__":
    unittest.main()
