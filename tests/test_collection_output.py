from pathlib import Path

import pytest

from vid_pipeline.collection_output import (
    infer_result_number,
    materialize_collection_output,
)
from vid_pipeline.github_client import GitHubRequest, GitHubState, sha256_file
from vid_pipeline.pyannote_cli import (
    _consume_collection_options,
    _materialize_collection_result,
)


def _three_files(root: Path) -> None:
    root.mkdir(parents=True)
    (root / "transcript.md").write_text("markdown\n", encoding="utf-8")
    (root / "transcript.timestamped.md").write_text("timed\n", encoding="utf-8")
    (root / "transcript.txt").write_text("text\n", encoding="utf-8")


def test_infer_result_number_from_tehran_filename():
    assert infer_result_number(Path("2.پلکان توانمندی مالی.m4v")) == 2
    assert infer_result_number(Path("anything.m4v"), 38) == 38


def test_materialize_collection_output_moves_three_files(tmp_path: Path):
    downloaded = tmp_path / ".vid_pipeline/github-results/request-2"
    _three_files(downloaded)
    collection = tmp_path / "outputs/uni_tehran"

    result = materialize_collection_output(
        downloaded, collection, Path("2.پلکان توانمندی مالی.m4v")
    )

    assert result == collection.resolve()
    assert (collection / "md/2.md").read_text(encoding="utf-8") == "markdown\n"
    assert (collection / "timestamped/2.md").read_text(encoding="utf-8") == "timed\n"
    assert (collection / "txt/2.txt").read_text(encoding="utf-8") == "text\n"
    assert not downloaded.exists()
    # The parent is shared by parallel GitHub submit workers and must remain.
    assert (tmp_path / ".vid_pipeline/github-results").is_dir()


def test_materialize_refuses_different_existing_output(tmp_path: Path):
    downloaded = tmp_path / "downloads/request-2"
    _three_files(downloaded)
    collection = tmp_path / "outputs/uni_tehran"
    (collection / "md").mkdir(parents=True)
    (collection / "md/2.md").write_text("different\n", encoding="utf-8")

    with pytest.raises(ValueError, match="different content"):
        materialize_collection_output(downloaded, collection, Path("2.test.m4v"))
    assert downloaded.exists()


def test_cli_collection_options_hide_download_workflow():
    argv = [
        "vid-pipeline",
        "github-submit-file",
        "2.test.m4v",
        "--repo",
        "owner/repo",
        "--collection-output-root",
        "outputs/uni_tehran",
        "--delete-result-artifact-after-save",
    ]

    prepared, root, number = _consume_collection_options(argv)

    assert root == Path("outputs/uni_tehran")
    assert number is None
    assert "--wait" in prepared
    assert "--download" in prepared
    assert "--delete-result-artifact-after-download" in prepared
    assert "--delete-result-artifact-after-save" not in prepared
    output_index = prepared.index("--output-root")
    assert prepared[output_index + 1] == ".vid_pipeline/github-results"


def test_materialize_collection_result_updates_saved_state(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    monkeypatch.chdir(tmp_path)
    source = tmp_path / "2.test.m4v"
    source.write_bytes(b"media")
    downloaded = tmp_path / ".vid_pipeline/github-results/request-2"
    _three_files(downloaded)
    state = GitHubState()
    state.save(
        GitHubRequest(
            request_id="request-2",
            local_path=str(source),
            file_size=source.stat().st_size,
            sha256=sha256_file(source),
            status="completed",
            output_path=str(downloaded),
        )
    )

    target = _materialize_collection_result(
        source,
        Path("outputs/uni_tehran"),
        None,
    )

    assert target == (tmp_path / "outputs/uni_tehran").resolve()
    assert (tmp_path / "outputs/uni_tehran/md/2.md").exists()
    assert state.load("request-2").output_path == str(target)
    assert not (tmp_path / ".vid_pipeline/github-results/request-2").exists()
    assert (tmp_path / ".vid_pipeline/github-results").is_dir()
