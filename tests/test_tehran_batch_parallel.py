import os
import subprocess
import textwrap
from pathlib import Path


def _write_executable(path: Path, content: str) -> None:
    path.write_text(content, encoding="utf-8")
    path.chmod(0o755)


def test_tehran_batch_runs_bounded_parallel_workers(tmp_path: Path):
    repo_root = Path(__file__).resolve().parents[1]
    script = repo_root / "scripts/run_tehran_batch.sh"

    input_dir = tmp_path / "input"
    output_dir = tmp_path / "output"
    bin_dir = tmp_path / "bin"
    state_file = tmp_path / "active.txt"
    input_dir.mkdir()
    bin_dir.mkdir()

    for number in (1, 2, 3):
        (input_dir / f"{number}.test.mp4").write_bytes(b"media")

    _write_executable(
        bin_dir / "vid-pipeline",
        textwrap.dedent(
            """\
            #!/usr/bin/env python3
            import fcntl
            import os
            import sys
            import time
            from pathlib import Path

            args = sys.argv[1:]
            def value(flag):
                return args[args.index(flag) + 1]

            out = Path(value("--collection-output-root"))
            number = value("--result-number")
            state = Path(os.environ["BATCH_TEST_STATE"])

            with state.open("a+") as handle:
                fcntl.flock(handle, fcntl.LOCK_EX)
                handle.seek(0)
                raw = handle.read().strip()
                active, maximum = map(int, raw.split(",")) if raw else (0, 0)
                active += 1
                maximum = max(maximum, active)
                handle.seek(0)
                handle.truncate()
                handle.write(f"{active},{maximum}")
                handle.flush()
                fcntl.flock(handle, fcntl.LOCK_UN)

            time.sleep(0.5)
            for folder, suffix in (("md", ".md"), ("timestamped", ".md"), ("txt", ".txt")):
                target = out / folder / f"{number}{suffix}"
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_text(f"video {number}\\n", encoding="utf-8")

            with state.open("r+") as handle:
                fcntl.flock(handle, fcntl.LOCK_EX)
                active, maximum = map(int, handle.read().strip().split(","))
                active -= 1
                handle.seek(0)
                handle.truncate()
                handle.write(f"{active},{maximum}")
                handle.flush()
                fcntl.flock(handle, fcntl.LOCK_UN)
            """
        ),
    )

    _write_executable(
        bin_dir / "vid-review",
        textwrap.dedent(
            """\
            #!/usr/bin/env python3
            import sys
            from pathlib import Path

            out = Path(sys.argv[2])
            number = sys.argv[3]
            for folder, suffix in (("md", ".md"), ("timestamped", ".md"), ("txt", ".txt")):
                target = out / "review" / folder / f"{number}{suffix}"
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_text(f"review {number}\\n", encoding="utf-8")
            """
        ),
    )

    env = os.environ.copy()
    env.update(
        {
            "PATH": f"{bin_dir}{os.pathsep}{env['PATH']}",
            "VID_PIPELINE_GITHUB_TOKEN": "test-token",
            "VID_PIPELINE_BATCH_INPUT": str(input_dir),
            "VID_PIPELINE_BATCH_OUTPUT": str(output_dir),
            "VID_PIPELINE_BATCH_START": "1",
            "VID_PIPELINE_BATCH_END": "3",
            "VID_PIPELINE_BATCH_PARALLEL": "2",
            "BATCH_TEST_STATE": str(state_file),
        }
    )

    result = subprocess.run(
        ["bash", str(script)],
        cwd=tmp_path,
        env=env,
        text=True,
        capture_output=True,
        timeout=20,
        check=False,
    )

    assert result.returncode == 0, result.stdout + result.stderr
    active, maximum = map(int, state_file.read_text(encoding="utf-8").split(","))
    assert active == 0
    assert maximum == 2
    assert "Parallel workers: 2" in result.stdout
    assert "Processing failures: none" in result.stdout
    assert "Review failures:     none" in result.stdout

    for number in (1, 2, 3):
        assert (output_dir / f"md/{number}.md").is_file()
        assert (output_dir / f"timestamped/{number}.md").is_file()
        assert (output_dir / f"txt/{number}.txt").is_file()
        assert (output_dir / f"review/md/{number}.md").is_file()
        assert (output_dir / f"review/timestamped/{number}.md").is_file()
        assert (output_dir / f"review/txt/{number}.txt").is_file()
