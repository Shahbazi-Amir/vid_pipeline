from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from vid_pipeline.download import download_video, extract_metadata


class FakeYoutubeDL:
    seen_options: list[dict[str, object]] = []

    def __init__(self, options: dict[str, object]) -> None:
        self.options = options
        self.__class__.seen_options.append(options)

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, traceback) -> None:
        return None

    def extract_info(self, url: str, download: bool = False):
        if download:
            output = Path(str(self.options["outtmpl"]).replace("%(ext)s", "mp4"))
            output.parent.mkdir(parents=True, exist_ok=True)
            output.write_bytes(b"video")
            return {"_filename": str(output), "duration": 10}
        return {"title": "Sample", "duration": 10}

    def sanitize_info(self, info):
        return info


class FakeYtDlp:
    YoutubeDL = FakeYoutubeDL


class DownloadOptionsTests(unittest.TestCase):
    def setUp(self) -> None:
        FakeYoutubeDL.seen_options.clear()

    @patch("vid_pipeline.download._yt_dlp_module", return_value=FakeYtDlp)
    def test_extract_metadata_can_disable_certificate_checks(self, _mock) -> None:
        extract_metadata("https://example.com/video", no_check_certificate=True)
        self.assertTrue(FakeYoutubeDL.seen_options[-1]["nocheckcertificate"])

    @patch("vid_pipeline.download._yt_dlp_module", return_value=FakeYtDlp)
    def test_download_can_disable_certificate_checks(self, _mock) -> None:
        with tempfile.TemporaryDirectory() as directory:
            video, metadata = download_video(
                "https://example.com/video",
                directory,
                no_check_certificate=True,
            )
        self.assertEqual(metadata["duration"], 10)
        self.assertEqual(video.suffix, ".mp4")
        self.assertTrue(FakeYoutubeDL.seen_options[-1]["nocheckcertificate"])


if __name__ == "__main__":
    unittest.main()
