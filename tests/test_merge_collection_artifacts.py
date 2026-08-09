from __future__ import annotations

import subprocess
import sys
from pathlib import Path


SCRIPT = Path(__file__).resolve().parents[1] / "scripts/merge_collection_artifacts.py"


def _write_result(root: Path, number: int, marker: str) -> None:
    for kind, suffix in (("md", "md"), ("timestamped", "md"), ("txt", "txt")):
        path = root / kind / f"{number}.{suffix}"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(f"{marker}-{kind}\n", encoding="utf-8")


def test_skip_existing_complete_base_preserves_main_result(tmp_path: Path) -> None:
    staging = tmp_path / "staging"
    target = tmp_path / "target"
    _write_result(staging, 3, "checkpoint")
    _write_result(target, 3, "main")

    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            str(staging),
            str(target),
            "--skip-existing-complete-base",
        ],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    assert (target / "md/3.md").read_text(encoding="utf-8") == "main-md\n"
    assert "Skipped 3 files" in result.stdout


def test_default_mode_still_rejects_different_existing_output(tmp_path: Path) -> None:
    staging = tmp_path / "staging"
    target = tmp_path / "target"
    _write_result(staging, 4, "checkpoint")
    _write_result(target, 4, "main")

    result = subprocess.run(
        [sys.executable, str(SCRIPT), str(staging), str(target)],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode != 0
    assert "refusing to overwrite different existing output" in result.stderr
