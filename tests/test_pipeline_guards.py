import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from vid_pipeline.errors import PipelineError
from vid_pipeline.models import EpisodeSpec
from vid_pipeline.pipeline import EpisodePipeline


class PipelineGuardTests(unittest.TestCase):
    def test_download_requires_verified_source_and_speaker(self):
        with tempfile.TemporaryDirectory() as directory:
            spec = EpisodeSpec(
                program="عصر شیرین",
                collection="asre-shirin-season-2",
                season="فصل دوم",
                season_episode=1,
                overall_episode=14,
                speaker="دکتر کمیل رودی",
                source_url="https://example.com/page",
                video_url="https://www.aparat.com/v/example",
            )
            pipeline = EpisodePipeline(spec, Path(directory))
            with patch("vid_pipeline.pipeline.download_video") as mocked:
                with self.assertRaises(PipelineError):
                    pipeline.download()
                mocked.assert_not_called()


if __name__ == "__main__":
    unittest.main()
