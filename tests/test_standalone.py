from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from vid_pipeline.standalone import VideoJobPaths, make_job_id


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
                paths.final_markdown,
                Path(directory) / "sample-12345678" / "final" / "transcript.final.md",
            )
            self.assertEqual(
                paths.final_text,
                Path(directory) / "sample-12345678" / "final" / "transcript.final.txt",
            )


if __name__ == "__main__":
    unittest.main()
