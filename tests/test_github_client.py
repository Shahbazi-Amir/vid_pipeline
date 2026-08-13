from __future__ import annotations

import io
import json
import subprocess
import zipfile
from pathlib import Path

import httpx
import pytest

from vid_pipeline import cli
from vid_pipeline.cli import build_parser
from vid_pipeline.github_client import (
    MAX_ASSET_SIZE,
    GitHubClient,
    GitHubRequest,
    GitHubState,
    detect_repository,
    discover_media,
    safe_asset_name,
    sha256_file,
)


def _result_zip(request_id: str) -> bytes:
    stream = io.BytesIO()
    with zipfile.ZipFile(stream, "w") as archive:
        archive.writestr("transcript.md", "# رونویسی نهایی\n")
        archive.writestr("transcript.txt", "رونویسی نهایی\n")
        archive.writestr("transcript.timestamped.md", "# زمان‌بندی‌شده\n")
    return stream.getvalue()


def test_discovery_is_recursive_and_naturally_sorted(tmp_path: Path):
    root = tmp_path / "input_videos"
    (root / "nested").mkdir(parents=True)
    for name in ("session-10.mp4", "session-2.mp4", "ignore.txt"):
        (root / name).write_bytes(b"x")
    (root / "nested" / "session-1.wav").write_bytes(b"x")
    assert [path.name for path in discover_media(root)] == [
        "session-2.mp4",
        "session-10.mp4",
    ]
    assert {path.name for path in discover_media(root, True)} == {
        "session-1.wav",
        "session-2.mp4",
        "session-10.mp4",
    }


def test_hash_asset_name_and_atomic_state(tmp_path: Path):
    media = tmp_path / "یک فایل بد!.mp4"
    media.write_bytes(b"media")
    digest = sha256_file(media)
    assert digest == "721c9525ade2ea8903d343ef25cf68b9bf4ab0aad56bb7b01fbe48d09bc7fcf4"
    name = safe_asset_name(media.name, digest)
    assert name.startswith(f"vp-{digest[:16]}-")
    assert "/" not in name
    state = GitHubState(tmp_path / ".vid_pipeline/github")
    request = GitHubRequest(request_id="request-1", sha256=digest)
    state.save(request)
    assert state.load("request-1").sha256 == digest
    assert not list(state.root.glob("*.tmp"))


def test_size_limit_rejects_two_gib_without_hashing(tmp_path: Path):
    media = tmp_path / "huge.mp4"
    with media.open("wb") as handle:
        handle.truncate(MAX_ASSET_SIZE)
    client = object.__new__(GitHubClient)
    client.state = GitHubState(tmp_path / "state")
    with pytest.raises(ValueError, match="too large"):
        client.create_file_request(media)


def test_repo_detection_from_environment(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("VID_PIPELINE_GITHUB_REPO", "owner/repository")
    assert detect_repository() == "owner/repository"


def test_repo_detection_from_git_remote(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.delenv("VID_PIPELINE_GITHUB_REPO", raising=False)

    class Result:
        stdout = "git@github.com:owner/repository.git\n"

    monkeypatch.setattr(subprocess, "run", lambda *args, **kwargs: Result())
    assert detect_repository() == "owner/repository"


def test_cli_commands_parse_without_worker_dependencies():
    commands = {
        "github-submit-file": ["github-submit-file", "input_videos/a.mp4"],
        "github-submit-folder": ["github-submit-folder", "input_videos", "--recursive"],
        "github-run-url": ["github-run-url", "https://example.com/video.mp4"],
        "github-job-status": ["github-job-status", "request-1"],
        "github-resume": ["github-resume", "request-1"],
        "github-cleanup": ["github-cleanup", "--stale"],
    }
    for command, argv in commands.items():
        assert build_parser().parse_args(argv).command == command
    assert "faster_whisper" not in __import__("sys").modules


@pytest.mark.parametrize(
    ("answer", "expected"),
    [("y", "y"), ("s", "s"), ("q", "q"), ("", "")],
)
def test_confirmation_requires_explicit_y(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    answer: str,
    expected: str,
):
    media = tmp_path / "clip.mp4"
    media.write_bytes(b"x")
    monkeypatch.setattr("builtins.input", lambda prompt: answer)
    assert cli._confirm_file(media) == expected


def test_folder_is_strictly_sequential_and_honors_skip_and_quit(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    root = tmp_path / "input"
    root.mkdir()
    for name in ("1.mp4", "2.mp4", "3.mp4"):
        (root / name).write_bytes(b"x")
    events: list[str] = []

    class FakeClient:
        def process_file(self, path: Path, **options):
            events.extend([f"upload:{path.name}", f"cleanup:{path.name}"])
            return GitHubRequest(request_id=path.stem, local_path=str(path), status="completed")

    answers = iter(["y", "s", "q"])
    monkeypatch.setattr("builtins.input", lambda prompt: next(answers))
    monkeypatch.setattr(cli, "_github_client", lambda args: FakeClient())
    args = build_parser().parse_args(["github-submit-folder", str(root)])
    assert cli.command_github_submit_folder(args) == 0
    assert events == ["upload:1.mp4", "cleanup:1.mp4"]


def test_uploaded_workflow_has_required_security_guards():
    workflow = (
        Path(__file__).resolve().parents[1]
        / ".github/workflows/process-uploaded-video.yml"
    ).read_text(encoding="utf-8")
    assert "run-name: Uploaded media ${{ inputs.request_id }}" in workflow
    assert "Authorization" in workflow
    assert "EXPECTED_SIZE" in workflow
    assert "EXPECTED_SHA256" in workflow
    assert "sudo apt-get install -y ffmpeg" in workflow
    assert "vid-pipeline \"${args[@]}\"" in workflow
    assert "retention-days: 1" in workflow
    assert "if: always()" in workflow
    artifact_section = workflow.split("name: Upload transcript result", 1)[1]
    assert "*.wav" not in artifact_section.split("name: Remove input", 1)[0]


def test_safe_zip_rejects_path_traversal(tmp_path: Path):
    archive = tmp_path / "bad.zip"
    with zipfile.ZipFile(archive, "w") as bundle:
        bundle.writestr("../../secret", "bad")
    with pytest.raises(ValueError, match="unsafe ZIP"):
        GitHubClient._safe_extract(archive, tmp_path / "output")
    assert not (tmp_path / "secret").exists()


def test_full_mock_github_flow_streams_and_deletes_only_after_validation(tmp_path: Path):
    media = tmp_path / "clip.mp4"
    media.write_bytes(b"x" * (2 * 1024 * 1024 + 7))
    request_id: list[str] = []
    dispatch_id: list[str] = []
    calls: list[str] = []
    archive = b""

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal archive
        calls.append(f"{request.method} {request.url.path}")
        path = request.url.path
        authenticated = "authorization" in request.headers
        if path == "/repos/owner/repo/releases" and request.method == "GET":
            return httpx.Response(200, json=[])
        if path == "/repos/owner/repo/releases" and request.method == "POST":
            return httpx.Response(
                201,
                json={
                    "id": 10,
                    "draft": True,
                    "upload_url": "https://uploads.github.test/releases/10/assets{?name,label}",
                },
            )
        if path == "/repos/owner/repo/releases/10/assets":
            return httpx.Response(200, json=[])
        if path == "/releases/10/assets" and request.method == "POST":
            assert int(request.headers["content-length"]) == media.stat().st_size
            assert len(request.read()) == media.stat().st_size
            return httpx.Response(
                201,
                json={
                    "id": 20,
                    "size": media.stat().st_size,
                    "state": "uploaded",
                    "digest": f"sha256:{sha256_file(media)}",
                    "browser_download_url": "https://github.test/private/asset",
                },
            )
        if path == "/private/asset" and not authenticated:
            return httpx.Response(404)
        if path.endswith("/actions/workflows/process-uploaded-video.yml/dispatches"):
            payload = json.loads(request.read())
            request_id.append(payload["inputs"]["request_id"])
            dispatch_id.append(payload["inputs"]["dispatch_id"])
            archive = _result_zip(request_id[0])
            return httpx.Response(204)
        if path.endswith("/actions/workflows/process-uploaded-video.yml/runs"):
            return httpx.Response(
                200,
                json={
                    "workflow_runs": [
                        {
                            "id": 30,
                            "status": "completed",
                            "conclusion": "success",
                            "display_title": (
                                f"Uploaded video {request_id[0]} — "
                                f"attempt {dispatch_id[0]}"
                            ),
                            "event": "workflow_dispatch",
                            "head_branch": "main",
                            "path": ".github/workflows/process-uploaded-video.yml",
                            "created_at": "2099-01-01T00:00:00Z",
                            "html_url": "https://github.test/run/30",
                        }
                    ]
                },
            )
        if path == "/repos/owner/repo/actions/runs/30/artifacts":
            return httpx.Response(
                200,
                json={
                    "artifacts": [
                        {
                            "id": 40,
                            "name": f"uploaded-transcript-{request_id[0]}",
                        }
                    ]
                },
            )
        if path == "/repos/owner/repo/actions/artifacts/40/zip":
            return httpx.Response(200, content=archive)
        if path == "/repos/owner/repo/releases/assets/20" and request.method == "DELETE":
            transcript = tmp_path / "outputs" / request_id[0] / "transcript.txt"
            assert transcript.read_text(encoding="utf-8").strip()
            return httpx.Response(204)
        raise AssertionError(f"unexpected request: {request.method} {request.url}")

    transport = httpx.MockTransport(handler)
    client = GitHubClient(
        "top-secret",
        "owner/repo",
        output_root=tmp_path / "outputs",
        state_root=tmp_path / "state",
        retries=0,
        transport=transport,
    )
    result = client.process_file(
        media,
        wait=True,
        download=True,
        delete_remote_after_success=True,
        no_editorial=True,
    )
    assert result.status == "completed"
    assert result.asset_id == 0
    assert media.exists()
    assert (tmp_path / "outputs" / result.job_id / "transcript.txt").exists()
    assert calls.index("POST /releases/10/assets") < calls.index(
        "POST /repos/owner/repo/actions/workflows/process-uploaded-video.yml/dispatches"
    )
    assert calls[-1] == "DELETE /repos/owner/repo/releases/assets/20"


def test_workflow_failure_keeps_remote_asset(tmp_path: Path):
    client = object.__new__(GitHubClient)
    client.state = GitHubState(tmp_path / "state")
    request = GitHubRequest(request_id="r1", asset_id=20, status="queued")
    client.state.save(request)
    client.find_run = lambda item: {
        "id": 30,
        "status": "completed",
        "conclusion": "failure",
        "html_url": "https://github.test/run",
    }
    result = client.wait(request, timeout=1)
    assert result["conclusion"] == "failure"
    assert request.status == "workflow_failed"
    assert request.asset_id == 20


def test_resume_workflow_failure_reuses_asset_without_upload(tmp_path: Path):
    media = tmp_path / "clip.mp4"
    media.write_bytes(b"unchanged")
    client = object.__new__(GitHubClient)
    client.state = GitHubState(tmp_path / "state")
    request = GitHubRequest(
        request_id="r1",
        local_path=str(media),
        original_name=media.name,
        safe_asset_name="vp-existing-clip.mp4",
        file_size=media.stat().st_size,
        sha256=sha256_file(media),
        release_id=10,
        asset_id=20,
        workflow_run_id=30,
        status="workflow_failed",
    )
    client.state.save(request)
    uploads: list[int] = []
    dispatches: list[int] = []
    client.upload_asset = lambda item: uploads.append(item.asset_id)

    def dispatch(item, options):
        dispatches.append(item.asset_id)
        item.workflow_run_id = 31
        item.status = "queued"
        client.state.save(item)

    client.dispatch_upload = dispatch
    client.wait = lambda item: {
        "id": 31,
        "status": "completed",
        "conclusion": "failure",
    }

    resumed = client.process_file(
        media,
        wait=True,
        download=False,
        delete_remote_after_success=False,
    )

    assert uploads == []
    assert dispatches == [20]
    assert resumed.asset_id == 20
    assert resumed.workflow_run_id == 31


def test_dispatching_resume_finds_existing_run_before_dispatch(tmp_path: Path):
    media = tmp_path / "clip.mp4"
    media.write_bytes(b"unchanged")
    client = object.__new__(GitHubClient)
    client.state = GitHubState(tmp_path / "state")
    request = GitHubRequest(
        request_id="r1",
        local_path=str(media),
        original_name=media.name,
        safe_asset_name="vp-existing-clip.mp4",
        file_size=media.stat().st_size,
        sha256=sha256_file(media),
        asset_id=20,
        dispatch_id="attempt-1",
        dispatch_started_at="2026-07-30T00:00:00+00:00",
        status="dispatching",
    )
    client.state.save(request)
    client.find_run = lambda item: setattr(item, "workflow_run_id", 31) or {
        "id": 31,
        "status": "queued",
    }
    client.dispatch_upload = lambda item, options: pytest.fail("duplicate dispatch")

    resumed = client.process_file(
        media,
        wait=False,
        download=False,
        delete_remote_after_success=False,
    )

    assert resumed.workflow_run_id == 31
    assert resumed.asset_id == 20


def test_dispatching_resume_does_not_redispatch_when_run_is_delayed(tmp_path: Path):
    media = tmp_path / "clip.mp4"
    media.write_bytes(b"unchanged")
    client = object.__new__(GitHubClient)
    client.state = GitHubState(tmp_path / "state")
    request = GitHubRequest(
        request_id="r1",
        local_path=str(media),
        original_name=media.name,
        safe_asset_name="vp-existing-clip.mp4",
        file_size=media.stat().st_size,
        sha256=sha256_file(media),
        asset_id=20,
        dispatch_id="attempt-1",
        dispatch_started_at="2026-07-30T00:00:00+00:00",
        status="dispatching",
    )
    client.state.save(request)
    client.recover_dispatched_run = lambda item: None
    client.dispatch_upload = lambda item, options: pytest.fail("duplicate dispatch")

    resumed = client.process_file(
        media,
        wait=False,
        download=False,
        delete_remote_after_success=False,
    )

    assert resumed.status == "dispatching"
    assert resumed.dispatch_id == "attempt-1"
    assert resumed.workflow_run_id == 0


def test_find_run_requires_exact_dispatch_correlation(tmp_path: Path):
    runs = [
        {
            "id": 30,
            "display_title": "Uploaded video r1 — attempt old-attempt",
            "event": "workflow_dispatch",
            "head_branch": "main",
            "path": ".github/workflows/process-uploaded-video.yml",
            "created_at": "2026-07-30T00:02:00Z",
        },
        {
            "id": 31,
            "display_title": "Uploaded video r1 — attempt current-attempt",
            "event": "workflow_dispatch",
            "head_branch": "other",
            "path": ".github/workflows/process-uploaded-video.yml",
            "created_at": "2026-07-30T00:02:00Z",
        },
        {
            "id": 32,
            "display_title": "Uploaded video r1 — attempt current-attempt",
            "event": "workflow_dispatch",
            "head_branch": "main",
            "path": ".github/workflows/other.yml",
            "created_at": "2026-07-30T00:02:00Z",
        },
        {
            "id": 33,
            "display_title": "Uploaded video r1 — attempt current-attempt",
            "event": "workflow_dispatch",
            "head_branch": "main",
            "path": ".github/workflows/process-uploaded-video.yml",
            "created_at": "2026-07-29T23:49:59Z",
        },
        {
            "id": 34,
            "display_title": "Uploaded video r1 — attempt current-attempt",
            "event": "workflow_dispatch",
            "head_branch": "main",
            "path": ".github/workflows/process-uploaded-video.yml@refs/heads/main",
            "created_at": "2026-07-30T00:02:00Z",
            "html_url": "https://github.test/run/34",
        },
    ]
    client = object.__new__(GitHubClient)
    client.repository = "owner/repo"
    client.ref = "main"
    client.state = GitHubState(tmp_path / "state")
    client._request = lambda *args, **kwargs: type(
        "Response", (), {"json": lambda self: {"workflow_runs": runs}}
    )()
    request = GitHubRequest(
        request_id="r1",
        dispatch_id="current-attempt",
        dispatch_started_at="2026-07-30T00:00:00+00:00",
    )

    run = client.find_run(request)

    assert run and run["id"] == 34
    assert request.workflow_run_id == 34


def test_find_run_accepts_seven_minute_client_clock_skew(tmp_path: Path):
    run = {
        "id": 30511226547,
        "display_title": (
            "Uploaded video 268249e8e85148769cc7536bb1df6093"
            " — attempt cef154c2cf3d4085ad982d7b91c68f33"
        ),
        "event": "workflow_dispatch",
        "head_branch": "agent/fix-github-dispatch-correlation",
        "path": ".github/workflows/process-uploaded-video.yml",
        "created_at": "2026-07-30T03:27:20Z",
    }
    client = object.__new__(GitHubClient)
    client.repository = "owner/repo"
    client.ref = "agent/fix-github-dispatch-correlation"
    client.state = GitHubState(tmp_path / "state")
    client._request = lambda *args, **kwargs: type(
        "Response", (), {"json": lambda self: {"workflow_runs": [run]}}
    )()
    request = GitHubRequest(
        request_id="268249e8e85148769cc7536bb1df6093",
        dispatch_id="cef154c2cf3d4085ad982d7b91c68f33",
        dispatch_started_at="2026-07-30T03:33:59.471114+00:00",
    )

    assert client.find_run(request) == run
    assert request.workflow_run_id == 30511226547


def test_find_run_rejects_run_older_than_clock_skew_tolerance(tmp_path: Path):
    run = {
        "id": 30,
        "display_title": "Uploaded video r1 — attempt current-attempt",
        "event": "workflow_dispatch",
        "head_branch": "main",
        "path": ".github/workflows/process-uploaded-video.yml",
        "created_at": "2026-07-30T00:49:59Z",
    }
    client = object.__new__(GitHubClient)
    client.repository = "owner/repo"
    client.ref = "main"
    client.state = GitHubState(tmp_path / "state")
    client._request = lambda *args, **kwargs: type(
        "Response", (), {"json": lambda self: {"workflow_runs": [run]}}
    )()
    request = GitHubRequest(
        request_id="r1",
        dispatch_id="current-attempt",
        dispatch_started_at="2026-07-30T01:00:00+00:00",
    )

    assert client.find_run(request) is None
    assert request.workflow_run_id == 0


@pytest.mark.parametrize("date_header", ["", "not a date"])
def test_dispatch_invalid_or_missing_server_date_falls_back_to_local_time(
    tmp_path: Path, date_header: str
):
    client = object.__new__(GitHubClient)
    client.repository = "owner/repo"
    client.ref = "main"
    client.state = GitHubState(tmp_path / "state")

    class Response:
        content = b""
        headers = {"Date": date_header} if date_header else {}

    client._request = lambda *args, **kwargs: Response()
    request = GitHubRequest(request_id="r1", asset_id=20)

    client.dispatch_upload(request, {})

    assert request.dispatch_server_at == ""
    assert request.dispatch_started_at
    assert request.status == "queued"


def test_dispatch_records_github_server_date(tmp_path: Path):
    client = object.__new__(GitHubClient)
    client.repository = "owner/repo"
    client.ref = "main"
    client.state = GitHubState(tmp_path / "state")

    class Response:
        content = b""
        headers = {"Date": "Thu, 30 Jul 2026 03:27:20 GMT"}

    client._request = lambda *args, **kwargs: Response()
    request = GitHubRequest(request_id="r1", asset_id=20)

    client.dispatch_upload(request, {})

    assert request.dispatch_server_at == "2026-07-30T03:27:20+00:00"


def test_old_state_without_dispatch_server_time_loads(tmp_path: Path):
    state = GitHubState(tmp_path / "state")
    state.path("old").write_text(
        '{"request_id":"old","dispatch_started_at":"2026-07-30T00:00:00+00:00"}',
        encoding="utf-8",
    )

    request = state.load("old")

    assert request.dispatch_server_at == ""


def test_completed_run_records_github_updated_at_and_clears_error(tmp_path: Path):
    client = object.__new__(GitHubClient)
    client.state = GitHubState(tmp_path / "state")
    request = GitHubRequest(
        request_id="r1",
        workflow_run_id=30,
        status="queued",
        last_error="old error",
    )
    client.find_run = lambda item: {
        "id": 30,
        "status": "completed",
        "conclusion": "success",
        "updated_at": "2026-07-30T03:40:12Z",
        "html_url": "https://github.test/run/30",
    }

    client.wait(request, timeout=1)

    loaded = client.state.load("r1")
    assert loaded.workflow_completed_at == "2026-07-30T03:40:12Z"
    assert loaded.workflow_run_id == 30
    assert loaded.workflow_run_url == "https://github.test/run/30"
    assert loaded.status == "workflow_succeeded"
    assert loaded.last_error == ""


def test_workflow_failure_stores_failed_step_without_secret(tmp_path: Path):
    client = object.__new__(GitHubClient)
    client.repository = "owner/repo"
    client.state = GitHubState(tmp_path / "state")
    request = GitHubRequest(
        request_id="r1", workflow_run_id=30, asset_id=20, status="queued"
    )
    client.find_run = lambda item: {
        "id": 30,
        "status": "completed",
        "conclusion": "failure",
    }
    client._request = lambda *args, **kwargs: type(
        "Response",
        (),
        {
            "json": lambda self: {
                "jobs": [
                    {
                        "name": "process",
                        "conclusion": "failure",
                        "steps": [
                            {
                                "name": "Download authenticated draft release asset",
                                "conclusion": "failure",
                            }
                        ],
                    }
                ]
            }
        },
    )()

    client.wait(request, timeout=1)

    assert "Download authenticated draft release asset" in request.last_error
    assert "token" not in request.last_error.lower()


def test_input_media_is_gitignored():
    repository = Path(__file__).resolve().parents[1]
    result = subprocess.run(
        ["git", "check-ignore", "--quiet", "input_videos/ignored-fixture.mp4"],
        cwd=repository,
    )
    assert result.returncode == 0


def test_token_is_not_saved_in_state(tmp_path: Path):
    state = GitHubState(tmp_path / "state")
    state.save(GitHubRequest(request_id="safe"))
    assert "top-secret" not in state.path("safe").read_text(encoding="utf-8")
    assert "TOKEN" not in {field.upper() for field in asdict_fields(GitHubRequest)}


def asdict_fields(cls: type) -> list[str]:
    return list(cls.__dataclass_fields__)
