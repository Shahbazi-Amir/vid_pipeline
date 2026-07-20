import unittest

from vid_pipeline.source import is_video_url, normalize_url


class SourceTests(unittest.TestCase):
    def test_video_hosts(self):
        self.assertTrue(is_video_url("https://www.aparat.com/v/example"))
        self.assertTrue(is_video_url("https://youtu.be/example"))
        self.assertFalse(is_video_url("https://example.com/page"))

    def test_normalize_url(self):
        self.assertEqual(
            normalize_url("https://example.com/a/", "../video"),
            "https://example.com/video",
        )


if __name__ == "__main__":
    unittest.main()
