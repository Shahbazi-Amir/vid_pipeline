import json
import tempfile
import unittest
from pathlib import Path

from vid_pipeline.models import EpisodeSpec
from vid_pipeline.paths import EpisodePaths
from vid_pipeline.state import PipelineState


class ModelsStateTests(unittest.TestCase):
    def sample_spec(self):
        return EpisodeSpec(
            program="عصر شیرین",
            collection="asre-shirin-season-2",
            season="فصل دوم",
            season_episode=1,
            overall_episode=14,
            speaker="دکتر کمیل رودی",
        )

    def test_spec_round_trip_and_paths(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "episode.json"
            spec = self.sample_spec()
            spec.save(path)
            loaded = EpisodeSpec.load(path)
            paths = EpisodePaths(Path(directory) / "work", loaded)
            self.assertEqual(loaded.record_id, "asre-shirin-season-2-01")
            self.assertIn("episode-01.raw.json", str(paths.raw_json))

    def test_state_requires_outputs_to_exist(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            output = root / "result.txt"
            output.write_text("ok", encoding="utf-8")
            state = PipelineState(root / "state.json")
            state.mark_complete("audio", [output])
            self.assertTrue(state.is_complete("audio"))
            output.unlink()
            state = PipelineState(root / "state.json")
            self.assertFalse(state.is_complete("audio"))
            data = json.loads((root / "state.json").read_text(encoding="utf-8"))
            self.assertIn("sha256", data["stages"]["audio"]["details"])


if __name__ == "__main__":
    unittest.main()
