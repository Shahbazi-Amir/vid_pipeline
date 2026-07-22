from __future__ import annotations

import unittest
from unittest.mock import patch

from vid_pipeline.download import _extract_info


class FakeYoutubeDL:
    attempts: list[dict[str, object]] = []

    def __init__(self, options: dict[str, object]) -> None:
        self.options = options
        self.attempts.append(options.copy())

    def __enter__(self) -> FakeYoutubeDL:
        return self

    def __exit__(self, exc_type, exc, traceback) -> None:
        return None

    def extract_info(self, url: str, download: bool) -> dict[str, object]:
        if not self.options.get("nocheckcertificate"):
            raise RuntimeError("CERTIFICATE_VERIFY_FAILED: hostname mismatch")
        return {"url": url, "download": download, "title": "sample"}

    def sanitize_info(self, info: dict[str, object]) -> dict[str, object]:
        return info


class FakeYtDlp:
    YoutubeDL = FakeYoutubeDL


class DownloadRetryTests(unittest.TestCase):
    def setUp(self) -> None:
        FakeYoutubeDL.attempts.clear()

    def test_certificate_failure_is_retried_without_verification(self) -> None:
        result = _extract_info(
            FakeYtDlp,
            "https://example.com/video",
            {"quiet": True},
            download=False,
        )

        self.assertEqual(result["title"], "sample")
        self.assertEqual(len(FakeYoutubeDL.attempts), 2)
        self.assertNotIn("nocheckcertificate", FakeYoutubeDL.attempts[0])
        self.assertTrue(FakeYoutubeDL.attempts[1]["nocheckcertificate"])

    @patch("vid_pipeline.download.time.sleep", return_value=None)
    def test_timeout_is_retried(self, sleep_mock) -> None:
        class TimeoutYoutubeDL(FakeYoutubeDL):
            calls = 0

            def extract_info(self, url: str, download: bool) -> dict[str, object]:
                type(self).calls += 1
                if type(self).calls < 3:
                    raise RuntimeError("Unable to download webpage: timed out")
                return {"url": url, "download": download, "title": "recovered"}

        class TimeoutYtDlp:
            YoutubeDL = TimeoutYoutubeDL

        result = _extract_info(
            TimeoutYtDlp,
            "https://example.com/slow",
            {"quiet": True},
            download=False,
        )

        self.assertEqual(result["title"], "recovered")
        self.assertEqual(TimeoutYoutubeDL.calls, 3)
        self.assertEqual(sleep_mock.call_count, 2)

    def test_non_retryable_failure_is_not_retried(self) -> None:
        class FailingYoutubeDL(FakeYoutubeDL):
            def extract_info(self, url: str, download: bool) -> dict[str, object]:
                raise RuntimeError("HTTP Error 404: Not Found")

        class FailingYtDlp:
            YoutubeDL = FailingYoutubeDL

        with self.assertRaisesRegex(RuntimeError, "404"):
            _extract_info(
                FailingYtDlp,
                "https://example.com/missing",
                {"quiet": True},
                download=False,
            )

        self.assertEqual(len(FakeYoutubeDL.attempts), 1)


if __name__ == "__main__":
    unittest.main()
