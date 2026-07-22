from __future__ import annotations

import unittest

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

    def test_non_certificate_failure_is_not_retried(self) -> None:
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
