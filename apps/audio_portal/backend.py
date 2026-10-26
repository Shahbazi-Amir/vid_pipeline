"""Durable GitHub Release -> commit queue -> existing ASR worker bridge."""
from __future__ import annotations

import base64
import hashlib
import json
import re
import time
from datetime import datetime, timezone
from pathlib import PurePath
from urllib.parse import quote

import httpx

BRANCH = "feature/hosted-audio-portal"
AUDIO_TYPES = {".mp3", ".m4a", ".wav", ".flac", ".aac", ".ogg", ".opus", ".wma", ".aiff", ".amr"}
MAX_BYTES = 500 * 1024 * 1024
JOB_PATTERN = re.compile(r"[a-f0-9]{32}")


class PortalError(RuntimeError):
    pass


def now():
    return datetime.now(timezone.utc).isoformat()


def validate_job(job):
    if not JOB_PATTERN.fullmatch(str(job.get("id", ""))):
        raise ValueError("Invalid job id")
    if job.get("language") not in {"fa", "ar"}:
        raise ValueError("Invalid language")
    if job.get("suffix") not in AUDIO_TYPES:
        raise ValueError("Unsupported audio format")
    if not isinstance(job.get("size"), int) or not 0 < job["size"] <= MAX_BYTES:
        raise ValueError("Invalid media size")
    if not re.fullmatch(r"[a-f0-9]{64}", str(job.get("sha256", ""))):
        raise ValueError("Invalid digest")
    if not isinstance(job.get("asset_id"), int) or job["asset_id"] <= 0:
        raise ValueError("Invalid asset id")
    if job.get("release_tag") != "rag_finance":
        raise ValueError("Unexpected release")
    if len(job.get("title", "")) > 160 or len(job.get("original_name", "")) > 255:
        raise ValueError("Name too long")
    return job


def make_job(job_id, name, data, asset_id, title, language):
    return validate_job({
        "version": 1, "id": job_id, "title": title.strip()[:160] or PurePath(name).stem[:160],
        "original_name": PurePath(name).name[:255], "suffix": PurePath(name).suffix.lower(),
        "size": len(data), "sha256": hashlib.sha256(data).hexdigest(),
        "asset_id": asset_id, "release_tag": "rag_finance", "language": language,
        "created_at": now(), "review": "pending_audio_and_quran_verification",
    })


class GitHubPortal:
    def __init__(self, token, repository="Shahbazi-Amir/vid_pipeline", branch=BRANCH, transport=None):
        if not token or not re.fullmatch(r"[\w.-]+/[\w.-]+", repository):
            raise PortalError("پیکربندی اتصال گیت‌هاب کامل نیست.")
        self.repository, self.branch = repository, branch
        self.client = httpx.Client(
            base_url="https://api.github.com", timeout=120, transport=transport,
            headers={"Authorization": f"Bearer {token}", "Accept": "application/vnd.github+json",
                     "X-GitHub-Api-Version": "2022-11-28"}, follow_redirects=False,
        )
        self.transport = transport

    def close(self):
        self.client.close()

    def request(self, method, path, **kw):
        try:
            response = self.client.request(method, f"/repos/{self.repository}{path}", **kw)
        except httpx.HTTPError:
            raise PortalError("ارتباط با گیت‌هاب قطع شد؛ دوباره وضعیت را بررسی کنید.") from None
        if response.status_code not in {200, 201, 204, 302, 404, 409, 422}:
            raise PortalError(f"درخواست گیت‌هاب ناموفق بود (کد {response.status_code}).")
        return response

    def read(self, path):
        response = self.request("GET", "/contents/" + path, params={"ref": self.branch})
        if response.status_code == 404:
            return None
        if response.status_code != 200:
            raise PortalError("خواندن فایل از مخزن ناموفق بود.")
        item = response.json()
        if item.get("encoding") == "none" or (not item.get("content") and item.get("size", 0)):
            blob = self.request("GET", "/git/blobs/" + item["sha"])
            if blob.status_code != 200:
                raise PortalError("خواندن فایل بزرگ از مخزن ناموفق بود.")
            item = blob.json()
        return {"data": base64.b64decode(item["content"]), "sha": item["sha"]}

    def write(self, path, data, message, *, replace=False):
        """Compare after ambiguous PUT; don't duplicate a queued transcription."""
        if isinstance(data, str):
            data = data.encode("utf-8")
        for attempt in range(5):
            previous = self.read(path)
            if previous and previous["data"] == data:
                return
            if previous and not replace:
                raise PortalError("این شناسه قبلاً ثبت شده است؛ فایل قبلی جایگزین نشد.")
            body = {"branch": self.branch, "message": message,
                    "content": base64.b64encode(data).decode()}
            if previous:
                body["sha"] = previous["sha"]
            try:
                response = self.request("PUT", "/contents/" + path, json=body)
                if response.status_code in {200, 201}:
                    return
                if response.status_code not in {409, 422}:
                    raise PortalError("ثبت فایل در مخزن ناموفق بود.")
            except PortalError:
                # A dropped response may follow a successful write. Verify before retrying.
                check = self.read(path)
                if check and check["data"] == data:
                    return
                if attempt == 4:
                    raise
            time.sleep(0.2 * (attempt + 1))
        raise PortalError("مخزن همزمان تغییر کرد؛ دوباره تلاش کنید.")

    def release(self):
        r = self.request("GET", "/releases/tags/rag_finance")
        if r.status_code != 200:
            raise PortalError("ریلیز rag_finance در دسترس نیست.")
        return r.json()

    def assets(self, release_id):
        found = []
        for page in range(1, 101):
            response = self.request("GET", f"/releases/{release_id}/assets", params={"per_page": 100, "page": page})
            if response.status_code != 200:
                raise PortalError("خواندن دارایی‌های ریلیز ناموفق بود.")
            rows = response.json()
            found.extend(rows)
            if len(rows) < 100:
                return found
        raise PortalError("تعداد فایل‌های ریلیز بیش از حد مجاز این نسخه است.")

    def upload(self, job_id, filename, data):
        suffix = PurePath(filename).suffix.lower()
        if not JOB_PATTERN.fullmatch(job_id) or suffix not in AUDIO_TYPES or not 0 < len(data) <= MAX_BYTES:
            raise PortalError("فایل صوتی معتبر با حجم حداکثر ۵۰۰ مگابایت انتخاب کنید.")
        release = self.release()
        name = f"portal-{job_id}{suffix}"
        digest = hashlib.sha256(data).hexdigest()
        existing = next((a for a in self.assets(release["id"]) if a["name"] == name), None)
        if existing:
            if existing["size"] != len(data) or existing.get("digest") not in {None, "sha256:" + digest} or existing.get("state") != "uploaded":
                raise PortalError("فایل هم‌نام ناقص یا متفاوت است؛ شناسهٔ تازه بسازید.")
            return existing["id"]
        url = f"https://uploads.github.com/repos/{self.repository}/releases/{int(release['id'])}/assets"
        try:
            response = self.client.post(url, params={"name": name}, content=bytes(data),
                                        headers={"Content-Type": "application/octet-stream"})
        except httpx.HTTPError:
            raise PortalError("آپلود کامل تأیید نشد؛ با همین فایل دوباره تلاش کنید.") from None
        if response.status_code != 201:
            raise PortalError(f"آپلود صوت ناموفق بود (کد {response.status_code}).")
        asset = response.json()
        if asset.get("size") != len(data) or asset.get("state") != "uploaded" or asset.get("digest") not in {None, "sha256:" + digest}:
            raise PortalError("اندازه یا هش فایل آپلودشده تأیید نشد.")
        return asset["id"]

    def enqueue(self, job):
        validate_job(job)
        self.write(f".portal/jobs/{job['id']}.json", json.dumps(job, ensure_ascii=False, indent=2) + "\n",
                   f"Audio portal {job['id']}")

    def jobs(self):
        # Git tree supports pagination-free discovery beyond the Contents API 1000-file cap.
        r = self.request("GET", "/git/trees/" + quote(self.branch, safe=""), params={"recursive": "1"})
        if r.status_code != 200:
            raise PortalError("خواندن فهرست کارها ناموفق بود.")
        tree = r.json()
        if tree.get("truncated"):
            raise PortalError("فهرست مخزن ناقص است؛ آرشیو کارها باید تفکیک شود.")
        return sorted((x["path"].split("/")[-1][:-5] for x in tree["tree"]
                       if re.fullmatch(r"\.portal/jobs/[a-f0-9]{32}\.json", x["path"])), reverse=True)

    def job(self, job_id):
        if not JOB_PATTERN.fullmatch(job_id):
            raise PortalError("شناسهٔ کار معتبر نیست.")
        source = self.read(f".portal/jobs/{job_id}.json")
        if source is None:
            raise PortalError("کار پیدا نشد.")
        return validate_job(json.loads(source["data"]))

    def status(self, job):
        result = self.read(f"outputs/audio-portal/{job['id']}/status.json")
        state = json.loads(result["data"]) if result else {"state": "queued"}
        if state["state"] == "completed":
            return state
        # Detect runner cancellations/timeouts, which cannot write their final status.
        runs = self.request("GET", "/actions/workflows/audio-portal.yml/runs",
                            params={"branch": self.branch, "per_page": 100})
        if runs.status_code == 200:
            for run in runs.json().get("workflow_runs", []):
                if run.get("display_title") == f"Audio portal {job['id']}":
                    state["run_url"] = run["html_url"]
                    if run["status"] == "completed" and run.get("conclusion") != "success":
                        state["state"] = run.get("conclusion") or "failed"
                    elif state["state"] == "queued" and run["status"] == "in_progress":
                        state["state"] = "preparing"
                    break
        return state

    def download_asset(self, asset_id, destination, expected_size, expected_sha):
        """Stream download; never forward the API credential to signed storage URLs."""
        response = self.request("GET", f"/releases/assets/{asset_id}", headers={"Accept": "application/octet-stream"})
        digest, size = hashlib.sha256(), 0
        def copy(chunks):
            nonlocal size
            with destination.open("wb") as f:
                for chunk in chunks:
                    size += len(chunk)
                    if size > expected_size:
                        raise PortalError("اندازهٔ فایل از مقدار ثبت‌شده بیشتر است.")
                    digest.update(chunk)
                    f.write(chunk)
        if response.status_code == 302:
            target = response.headers["location"]
            if not target.startswith("https://"):
                raise PortalError("نشانی دانلود امن نیست.")
            with httpx.Client(transport=self.transport, follow_redirects=True, timeout=120) as public:
                with public.stream("GET", target) as stream:
                    stream.raise_for_status()
                    copy(stream.iter_bytes())
        elif response.status_code == 200:
            copy([response.content])
        else:
            raise PortalError("دریافت صوت ناموفق بود.")
        if size != expected_size or digest.hexdigest() != expected_sha:
            raise PortalError("هش یا اندازهٔ صوت با فایل اولیه مطابقت ندارد.")
