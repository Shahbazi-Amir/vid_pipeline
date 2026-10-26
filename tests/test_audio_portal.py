"""Integration checks for upload integrity, durable queue recovery, and draft isolation."""
import base64
import hashlib
import importlib.util
import json
import sys
from pathlib import Path

import httpx
import pytest
import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "apps/audio_portal"))
from backend import BRANCH, GitHubPortal, PortalError, make_job, validate_job

JOB_ID = "1" * 32
DATA = b"audio-fixture"
DIGEST = hashlib.sha256(DATA).hexdigest()


def job():
    return make_job(JOB_ID, "جلسه.m4a", DATA, 42, "جلسه آزمایشی", "fa")


def response(request, status=200, **body):
    return httpx.Response(status, request=request, json=body)


@pytest.mark.parametrize("field,value", [("id", "../escape"), ("size", 0), ("sha256", "bad"),
    ("language", "fa;curl evil"), ("suffix", ".zip"), ("release_tag", "other"), ("asset_id", -2)])
def test_reject_untrusted_manifest(field, value):
    with pytest.raises(ValueError):
        validate_job(dict(job(), **{field: value}))


def test_manifest_keeps_persian_and_quran_review_pending():
    j = job()
    assert j["original_name"] == "جلسه.m4a"
    assert j["review"] == "pending_audio_and_quran_verification"
    assert j["sha256"] == DIGEST


def test_ambiguous_queue_write_is_verified_without_duplicate():
    saved, writes = {}, []
    def handler(req):
        if req.method == "GET":
            if not saved:
                return response(req, 404)
            return response(req, content=base64.b64encode(saved["data"]).decode(), sha="a")
        writes.append(req)
        body = json.loads(req.content)
        assert body["branch"] == BRANCH
        assert body["message"] == "Audio portal " + JOB_ID
        saved["data"] = base64.b64decode(body["content"])
        raise httpx.ReadTimeout("lost response", request=req)
    gh = GitHubPortal("secret", transport=httpx.MockTransport(handler))
    gh.enqueue(job())
    assert len(writes) == 1
    assert json.loads(saved["data"])["id"] == JOB_ID
    gh.close()


def test_upload_is_verified_and_reused():
    calls = []
    def handler(req):
        calls.append(req)
        if req.url.path.endswith("/tags/rag_finance"):
            return response(req, id=7)
        if req.method == "GET":
            return httpx.Response(200, request=req, json=[{"name": "portal-" + JOB_ID + ".m4a", "id": 42,
                 "size": len(DATA), "digest": "sha256:" + DIGEST, "state": "uploaded"}])
        pytest.fail("Should not upload a duplicate")
    gh = GitHubPortal("secret", transport=httpx.MockTransport(handler))
    assert gh.upload(JOB_ID, "جلسه.m4a", DATA) == 42
    assert all(r.method == "GET" for r in calls)
    gh.close()


def test_signed_download_never_forwards_github_token(tmp_path):
    def handler(req):
        if req.url.host == "api.github.com":
            assert req.headers["Authorization"] == "Bearer secret"
            return httpx.Response(302, request=req, headers={"Location": "https://storage.example/audio"})
        assert "authorization" not in req.headers
        return httpx.Response(200, request=req, content=DATA)
    gh = GitHubPortal("secret", transport=httpx.MockTransport(handler))
    target = tmp_path / "audio.m4a"
    gh.download_asset(42, target, len(DATA), DIGEST)
    assert target.read_bytes() == DATA
    with pytest.raises(PortalError):
        gh.download_asset(42, target, len(DATA), "0" * 64)
    gh.close()


def test_timeout_overrides_stale_running_state():
    def handler(req):
        if "/contents/" in req.url.path:
            return response(req, content=base64.b64encode(b'{"state":"transcribing"}').decode(), sha="x")
        return response(req, workflow_runs=[{"display_title": "Audio portal " + JOB_ID, "html_url": "https://github.com/run", "status": "completed", "conclusion": "timed_out"}])
    gh = GitHubPortal("secret", transport=httpx.MockTransport(handler))
    assert gh.status(job())["state"] == "timed_out"
    gh.close()


def test_large_raw_json_uses_git_blob():
    content = b'{"segments":[]}'
    def handler(req):
        if "/contents/" in req.url.path:
            return response(req, encoding="none", content="", size=1500000, sha="abc")
        assert req.url.path.endswith("/git/blobs/abc")
        return response(req, content=base64.b64encode(content).decode(), sha="abc")
    gh = GitHubPortal("secret", transport=httpx.MockTransport(handler))
    assert gh.read("outputs/audio-portal/raw.json")["data"] == content
    gh.close()


def test_worker_preserves_complete_draft_and_never_invokes_review(tmp_path, monkeypatch):
    spec = importlib.util.spec_from_file_location("portal_worker", ROOT / "scripts/audio_portal_worker.py")
    worker = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(worker)
    monkeypatch.chdir(tmp_path)
    class FakeGitHub:
        repository = "Shahbazi-Amir/vid_pipeline"
        writes = {}
        def read(self, path):
            return None
        def release(self):
            return {"id": 7}
        def assets(self, _):
            return [{"id": 42, "name": "portal-" + JOB_ID + ".m4a", "size": len(DATA)}]
        def download_asset(self, _, destination, size, sha):
            destination.write_bytes(DATA)
        def write(self, path, data, message, **kw):
            self.writes[path] = data
    full = "ماموریت فردی؛ بسم الله الرحمن الرحیم.\n" * 100
    def process(args, **kw):
        assert "--no-editorial" in args and "--language" in args
        root = tmp_path / "portal-work/job"
        for folder, name in [("final", "transcript.final.md"), ("final", "transcript.final.txt"),
                              ("raw", "transcript.raw.md"), ("raw", "transcript.raw.json")]:
            p = root / folder / name
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(full if not name.endswith("json") else '{"segments":[]}', encoding="utf-8")
        return type("Result", (), {"returncode": 0})()
    monkeypatch.setattr(worker.subprocess, "run", process)
    gh = FakeGitHub()
    worker.run(gh, job())
    base = "outputs/audio-portal/" + JOB_ID + "/"
    assert gh.writes[base + "transcript.txt"].decode() == full
    assert json.loads(gh.writes[base + "status.json"])["state"] == "completed"
    assert json.loads(gh.writes[base + "source.json"])["reviewed"] is False


def test_streamlit_login_and_authenticated_upload_view(monkeypatch):
    from streamlit.testing.v1 import AppTest
    monkeypatch.setenv("PORTAL_ACCESS_PASSWORD", "test-only")
    monkeypatch.setenv("VID_PIPELINE_GITHUB_TOKEN", "test-only")
    for key in ["ALL_PROXY", "HTTP_PROXY", "HTTPS_PROXY", "all_proxy", "http_proxy", "https_proxy"]:
        monkeypatch.delenv(key, raising=False)
    # Dashboard should remain empty and never contact a real service.
    monkeypatch.setattr(GitHubPortal, "jobs", lambda self: [])
    app = AppTest.from_file(str(ROOT / "apps/audio_portal/app.py")).run(timeout=20)
    assert not app.exception
    assert any("رمز ورود" in x.label for x in app.text_input)
    app.session_state["authenticated"] = True
    app.run(timeout=20)
    assert not app.exception
    assert any("بارگذاری و شروع" in x.label for x in app.button)


def test_workflow_is_branch_scoped_and_does_not_cancel_other_jobs():
    # BaseLoader preserves the YAML 'on' key.
    workflow = yaml.load((ROOT / ".github/workflows/audio-portal.yml").read_text(), Loader=yaml.BaseLoader)
    assert workflow["on"]["push"]["branches"] == [BRANCH]
    assert workflow["on"]["push"]["paths"] == [".portal/jobs/*.json"]
    assert workflow["jobs"]["transcribe"]["concurrency"]["cancel-in-progress"] == "false"
    assert workflow["jobs"]["transcribe"]["timeout-minutes"] == "350"
