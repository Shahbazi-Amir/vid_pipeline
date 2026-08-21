"""Local Streamlit console for submitting and observing transcription jobs."""

from __future__ import annotations

import hashlib
import os
from pathlib import Path
from typing import Any

import streamlit as st

from vid_pipeline.online_client import OnlineClient
from vid_pipeline.profiles import SUPPORTED_PROFILES
from vid_pipeline.web_utils import (
    ACTIVE_JOB_STATUSES,
    RETRYABLE_JOB_STATUSES,
    STAGE_LABELS,
    downloadable_artifacts,
    format_duration,
    job_timing,
    parse_release_lines,
    parse_url_lines,
    preferred_text_artifact,
    source_label,
    stage_rows,
)

STATUS_LABELS = {
    "queued": "در صف",
    "preparing": "آماده‌سازی",
    "processing": "در حال پردازش",
    "quality_check": "کنترل کیفیت",
    "rendering": "ساخت خروجی",
    "completed": "تکمیل‌شده",
    "review_required": "نیازمند بازبینی",
    "failed": "ناموفق",
    "cancelled": "لغوشده",
}
STATUS_ICON = {
    "queued": "🕓",
    "preparing": "📥",
    "processing": "⚙️",
    "quality_check": "🧪",
    "rendering": "📝",
    "completed": "✅",
    "review_required": "🟠",
    "failed": "❌",
    "cancelled": "⏹️",
}

st.set_page_config(
    page_title="Media Transcript Console",
    page_icon="🎙️",
    layout="wide",
)

SERVER_URL = os.getenv("VID_PIPELINE_SERVER_URL", "http://api:8000")
API_TOKEN = os.getenv("VID_PIPELINE_API_TOKEN", "")
WEB_ROOT = Path(os.getenv("VID_PIPELINE_WEB_ROOT", "/data/web")).resolve()
WEB_ROOT.mkdir(parents=True, exist_ok=True)


@st.cache_resource
def _client(server_url: str, api_token: str, root: str) -> OnlineClient:
    base = Path(root)
    return OnlineClient(
        server_url,
        api_token,
        output_root=base / "downloads",
        state_root=base / "client-state",
        timeout=120,
        retries=2,
    )


client = _client(SERVER_URL, API_TOKEN, str(WEB_ROOT))


def _persist_uploaded_file(uploaded: Any) -> Path:
    safe_name = Path(uploaded.name).name
    buffer = uploaded.getbuffer()
    digest = hashlib.sha256(buffer).hexdigest()
    target = WEB_ROOT / "uploads" / digest[:16] / safe_name
    target.parent.mkdir(parents=True, exist_ok=True)
    if not target.is_file() or target.stat().st_size != len(buffer):
        with target.open("wb") as handle:
            handle.write(buffer)
    return target


def _job_options() -> dict[str, Any]:
    return {
        "profile": st.session_state.get("profile", "balanced"),
        "language": st.session_state.get("language", "fa"),
        "audio_profile": st.session_state.get("audio_profile", "safe"),
        "editorial": False,
    }


def _submit_files(files: list[Any]) -> None:
    if not files:
        st.warning("حداقل یک فایل صوتی یا ویدیویی انتخاب کنید.")
        return
    options = _job_options()
    progress = st.progress(0, text="در حال ثبت فایل‌ها…")
    successes = 0
    for index, uploaded in enumerate(files, 1):
        try:
            path = _persist_uploaded_file(uploaded)
            client.submit_file(path, **options)
            successes += 1
        except Exception as exc:
            st.error(f"{uploaded.name}: {type(exc).__name__}: {exc}")
        progress.progress(index / len(files), text=f"ثبت {index} از {len(files)}")
    if successes:
        st.success(f"{successes} Job ثبت شد و وارد صف پردازش شد.")


def _submit_urls(value: str) -> None:
    urls = parse_url_lines(value)
    if not urls:
        st.warning("حداقل یک URL وارد کنید.")
        return
    options = _job_options()
    successes = 0
    for url in urls:
        try:
            client.submit_url(url, **options)
            successes += 1
        except Exception as exc:
            st.error(f"{url}: {type(exc).__name__}: {exc}")
    if successes:
        st.success(f"{successes} URL به صف اضافه شد.")


def _submit_releases(value: str) -> None:
    try:
        releases = parse_release_lines(value)
    except ValueError as exc:
        st.error(str(exc))
        return
    if not releases:
        st.warning("حداقل یک GitHub Release asset وارد کنید.")
        return
    options = _job_options()
    successes = 0
    for release in releases:
        try:
            client.submit_github_release(**release, **options)
            successes += 1
        except Exception as exc:
            label = f"{release['repository']}@{release['tag']} / {release['asset']}"
            st.error(f"{label}: {type(exc).__name__}: {exc}")
    if successes:
        st.success(f"{successes} Release asset به صف اضافه شد.")


def _artifact_bytes(job_id: str, name: str) -> bytes:
    response = client._request("GET", f"/v1/jobs/{job_id}/artifacts/{name}")
    return bytes(response.content)


def _artifacts(job_id: str) -> list[dict[str, Any]]:
    return client._request("GET", f"/v1/jobs/{job_id}/artifacts").json()["artifacts"]


def _render_job_detail(job: dict[str, Any]) -> None:
    job_id = str(job["job_id"])
    status = str(job.get("status") or "")
    stage = str(job.get("current_stage") or status)
    timing = job_timing(job)

    st.subheader(f"{STATUS_ICON.get(status, '•')} {source_label(job)}")
    st.caption(f"Job ID: `{job_id}` · Profile: `{job.get('profile', '')}` · Model: `{job.get('model', '')}`")
    st.progress(
        min(100, max(0, int(job.get("progress_percent", 0) or 0))) / 100,
        text=f"{STAGE_LABELS.get(stage, stage)} — {int(job.get('progress_percent', 0) or 0)}%",
    )

    metrics = st.columns(6)
    metrics[0].metric("وضعیت", STATUS_LABELS.get(status, status))
    metrics[1].metric("مدت ورودی", format_duration(job.get("input_duration_seconds")))
    metrics[2].metric("مدت متن زمان‌دار", format_duration(job.get("output_duration_seconds")))
    metrics[3].metric("انتظار در صف", format_duration(timing["queue_wait_seconds"]))
    metrics[4].metric("زمان اجرا", format_duration(timing["execution_seconds"]))
    metrics[5].metric("کل زمان", format_duration(timing["total_seconds"]))

    times = st.columns(3)
    times[0].caption(f"ثبت ورودی: `{job.get('created_at') or '—'}`")
    times[1].caption(f"شروع اجرا: `{job.get('started_at') or '—'}`")
    times[2].caption(f"پایان: `{job.get('completed_at') or '—'}`")

    history = stage_rows(job)
    with st.expander("مراحل اجرا و زمان هر مرحله", expanded=status in ACTIVE_JOB_STATUSES):
        st.dataframe(
            [
                {
                    "مرحله": row["label"],
                    "وضعیت": {"done": "✅", "active": "▶️", "pending": "○"}.get(row["state"], row["state"]),
                    "زمان ورود": row.get("at") or "—",
                    "درصد": row.get("progress_percent") if row.get("progress_percent") is not None else "—",
                }
                for row in history
            ],
            use_container_width=True,
            hide_index=True,
        )
        stage_timings = job.get("stage_timings") or {}
        if stage_timings:
            st.caption("زمان‌های اندازه‌گیری‌شده داخل هسته پردازش")
            st.json(stage_timings)

    quality = job.get("quality_gate") or {}
    if quality:
        score = quality.get("overall_score")
        if score is not None:
            st.metric("امتیاز کیفیت", f"{float(score):.1f}/100")
        reasons = quality.get("reasons") or []
        if reasons:
            st.warning("علت نیاز به بازبینی: " + ", ".join(map(str, reasons)))

    if status == "review_required":
        st.warning(
            "رونویسی پایه تمام شده اما Quality Gate آن را Final نکرده است. "
            "متن Machine Draft برای بازبینی بعدی قابل مشاهده و دانلود است."
        )
    if job.get("error"):
        st.error(str(job["error"]))

    action_cols = st.columns([1, 1, 4])
    if status in ACTIVE_JOB_STATUSES:
        if action_cols[0].button("لغو Job", key=f"cancel-{job_id}"):
            try:
                client._request("POST", f"/v1/jobs/{job_id}/cancel")
                st.rerun()
            except Exception as exc:
                st.error(f"لغو ناموفق بود: {exc}")
    if status in RETRYABLE_JOB_STATUSES:
        if action_cols[1].button("اجرای مجدد", key=f"retry-{job_id}"):
            try:
                client._request("POST", f"/v1/jobs/{job_id}/retry")
                st.rerun()
            except Exception as exc:
                st.error(f"Retry ناموفق بود: {exc}")

    if status not in {"completed", "review_required"}:
        return
    try:
        artifacts = _artifacts(job_id)
    except Exception as exc:
        st.error(f"خواندن Artifactها ناموفق بود: {exc}")
        return
    names = [str(item["name"]) for item in artifacts]
    text_name = preferred_text_artifact(names, status)
    if text_name:
        try:
            text_bytes = _artifact_bytes(job_id, text_name)
            text = text_bytes.decode("utf-8", errors="replace")
            st.text_area("متن رونویسی", text, height=360, disabled=True)
        except Exception as exc:
            st.error(f"نمایش متن ناموفق بود: {exc}")

    download_names = downloadable_artifacts(names)
    if download_names:
        st.markdown("#### دانلود خروجی‌ها")
        columns = st.columns(min(4, len(download_names)))
        for index, name in enumerate(download_names):
            try:
                data = _artifact_bytes(job_id, name)
            except Exception:
                continue
            columns[index % len(columns)].download_button(
                label=f"دانلود {Path(name).name}",
                data=data,
                file_name=Path(name).name,
                mime="text/plain" if name.endswith((".txt", ".md", ".srt", ".vtt")) else "application/json",
                key=f"download-{job_id}-{index}",
            )


st.title("🎙️ Media Transcript Console")
st.caption(
    "ورودی فایل/صوت/ویدیو، URL یا GitHub Release → صف پردازش → رونویسی → Quality Gate → متن قابل دانلود. "
    "بازبینی عمیق انسانی/AI عمداً مرحله بعدی و جداگانه است."
)

with st.sidebar:
    st.header("تنظیمات رونویسی")
    st.selectbox("Profile", list(SUPPORTED_PROFILES), index=1, key="profile")
    st.text_input("Language", value="fa", key="language")
    st.selectbox("Audio profile", ["safe", "none", "noisy"], index=0, key="audio_profile")
    st.divider()
    st.caption(f"API: `{SERVER_URL}`")
    st.caption("برای اجرای واقعاً موازی، چند Worker RQ در Docker Compose Scale می‌شوند.")

submit_tab, jobs_tab = st.tabs(["➕ ورودی جدید", "📊 Jobها و خروجی‌ها"])

with submit_tab:
    file_tab, url_tab, release_tab = st.tabs(["فایل", "URL", "GitHub Release"])
    with file_tab:
        files = st.file_uploader(
            "یک یا چند فایل صوتی/ویدیویی",
            type=[
                "aac", "ac3", "aif", "aiff", "alac", "amr", "avi", "caf", "flac", "m4a", "m4v",
                "mkv", "mov", "mp3", "mp4", "ogg", "opus", "wav", "webm", "wma",
            ],
            accept_multiple_files=True,
        )
        if st.button("ثبت فایل‌ها و شروع", type="primary", key="submit-files"):
            _submit_files(list(files or []))
    with url_tab:
        urls = st.text_area(
            "URLها — هر خط یک لینک",
            placeholder="https://example.com/audio.mp3\nhttps://example.com/video.mp4",
            height=140,
        )
        if st.button("ثبت URLها", type="primary", key="submit-urls"):
            _submit_urls(urls)
    with release_tab:
        releases = st.text_area(
            "هر خط: owner/repo | tag | asset",
            placeholder="owner/repo | v1.0.0 | interview.mp3",
            height=140,
        )
        st.caption("برای Release خصوصی، `VID_PIPELINE_GITHUB_TOKEN` روی Worker تنظیم می‌شود.")
        if st.button("ثبت Releaseها", type="primary", key="submit-releases"):
            _submit_releases(releases)

with jobs_tab:
    st.caption("این بخش هر ۳ ثانیه تازه می‌شود. چند Job می‌توانند همزمان در Workerهای مختلف اجرا شوند.")

    @st.fragment(run_every="3s")
    def jobs_dashboard() -> None:
        try:
            jobs = client.jobs()
        except Exception as exc:
            st.error(f"API در دسترس نیست: {type(exc).__name__}: {exc}")
            return
        jobs = sorted(jobs, key=lambda item: str(item.get("created_at") or ""), reverse=True)
        if not jobs:
            st.info("هنوز Jobی ثبت نشده است.")
            return
        active = sum(str(job.get("status")) in ACTIVE_JOB_STATUSES for job in jobs)
        completed = sum(str(job.get("status")) == "completed" for job in jobs)
        needs_review = sum(str(job.get("status")) == "review_required" for job in jobs)
        top = st.columns(4)
        top[0].metric("کل Jobها", len(jobs))
        top[1].metric("فعال/در صف", active)
        top[2].metric("تکمیل‌شده", completed)
        top[3].metric("نیازمند بازبینی", needs_review)

        table = []
        for job in jobs[:100]:
            timing = job_timing(job)
            table.append(
                {
                    "Job": str(job["job_id"])[:10],
                    "ورودی": source_label(job),
                    "وضعیت": STATUS_LABELS.get(str(job.get("status")), str(job.get("status"))),
                    "مرحله": STAGE_LABELS.get(str(job.get("current_stage")), str(job.get("current_stage"))),
                    "%": int(job.get("progress_percent", 0) or 0),
                    "مدت ورودی": format_duration(job.get("input_duration_seconds")),
                    "زمان اجرا": format_duration(timing["execution_seconds"]),
                }
            )
        st.dataframe(table, use_container_width=True, hide_index=True)

        options = [str(job["job_id"]) for job in jobs]
        selected = st.selectbox(
            "جزئیات Job",
            options,
            format_func=lambda job_id: next(
                f"{STATUS_ICON.get(str(job.get('status')), '•')} {source_label(job)} — {job_id[:10]}"
                for job in jobs if str(job["job_id"]) == job_id
            ),
            key="selected-job",
        )
        selected_job = next(job for job in jobs if str(job["job_id"]) == selected)
        _render_job_detail(selected_job)

    jobs_dashboard()
