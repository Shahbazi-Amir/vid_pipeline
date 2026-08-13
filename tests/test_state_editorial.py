from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from vid_pipeline.state import PipelineState


class StateEditorialTests(unittest.TestCase):
    def test_new_editorial_stages_exist(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            state = PipelineState(Path(directory) / "state.json")
            self.assertEqual(state.stage("editorial")["status"], "pending")
            self.assertEqual(state.stage("finalize_machine")["status"], "pending")
            self.assertEqual(state.stage("chatgpt_review")["status"], "pending")


if __name__ == "__main__":
    unittest.main()
