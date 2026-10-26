"""Persian, cloud-ready Streamlit console; ASR runs durably in GitHub Actions."""
from __future__ import annotations

import hashlib
import hmac
import io
import json
import os
import sys
import uuid
import zipfile
from pathlib import Path

import streamlit as st

sys.path.insert(0, str(Path(__file__).parent))
from backend import AUDIO_TYPES, GitHubPortal, PortalError, make_job

st.set_page_config(page_title="گفتار | تبدیل صوت به متن", page_icon="🎙️", layout="wide")
st.markdown("""<style>
@import url('https://fonts.googleapis.com/css2?family=Vazirmatn:wght@400;500;600;700;800&display=swap');
html,body,[data-testid="stApp"],button,input,textarea {font-family:Vazirmatn,Tahoma,sans-serif!important}
[data-testid="stAppViewContainer"] {background:#f5f7fa;direction:rtl;text-align:right}
[data-testid="stMainBlockContainer"] {max-width:1120px;padding-top:2rem}
[data-testid="stSidebar"] {background:#edf1f7;direction:rtl}
[data-testid="stVerticalBlockBorderWrapper"] {background:white;border-radius:18px}
h1,h2,h3,p,label {text-align:right}
textarea {direction:rtl;text-align:right;line-height:1.95!important}
.stButton button[kind="primary"] {background:#245d68;border:0;border-radius:10px}
.hero {padding:30px 32px;background:#143b45;color:white;border-radius:20px;margin:0 0 24px}
.hero h1 {color:white;font-size:2.3rem;margin:0 0 8px}.hero p {color:#d2e6e9;margin:0;line-height:1.9}
.eyebrow {font-size:.8rem;letter-spacing:.08em;color:#a9d9d3;margin-bottom:12px}
.step {padding:14px;background:#eaf0f2;border-radius:12px;color:#27515b;margin-bottom:18px}
</style>""", unsafe_allow_html=True)


def setting(name, default=""):
    value = os.getenv(name)
    if value:
        return value
    try:
        return str(st.secrets.get(name, default))
    except FileNotFoundError:
        return default


def authenticate():
    password = setting("PORTAL_ACCESS_PASSWORD")
    if not password:
        st.error("راه‌اندازی کامل نشده: رمز ورود باید در تنظیمات امن میزبان ثبت شود.")
        st.stop()
    if st.session_state.get("authenticated"):
        return
    st.markdown('<div class="hero"><div class="eyebrow">VID PIPELINE</div><h1>گفتار، ماندگار می‌شود.</h1><p>فضای تبدیل صوت فارسی و عربی به متن قابل مطالعه</p></div>', unsafe_allow_html=True)
    with st.form("login"):
        supplied = st.text_input("رمز ورود", type="password")
        submitted = st.form_submit_button("ورود به کارگاه", type="primary")
    if submitted:
        if hmac.compare_digest(supplied.encode(), password.encode()):
            st.session_state.authenticated = True
            st.rerun()
        st.error("رمز ورود درست نیست.")
    st.stop()


authenticate()
token = setting("VID_PIPELINE_GITHUB_TOKEN")
if not token:
    st.error("اتصال گیت‌هاب هنوز در تنظیمات امن میزبان ثبت نشده است.")
    st.stop()


def client():
    return GitHubPortal(token, repository=setting("VID_PIPELINE_GITHUB_REPO", "Shahbazi-Amir/vid_pipeline"))


LABELS = {"queued": "در صف شروع", "preparing": "آماده‌سازی موتور", "downloading": "دریافت و کنترل صوت",
          "transcribing": "تبدیل صوت به متن", "publishing": "ذخیرهٔ متن", "completed": "متن اولیه آماده است",
          "failed": "پردازش ناموفق", "failure": "پردازش ناموفق", "cancelled": "لغوشده", "timed_out": "پایان مهلت اجرا"}

st.markdown('<div class="hero"><div class="eyebrow">کارگاه صوت و متن · VID PIPELINE</div><h1>از صدا، به کلمه.</h1><p>صوت را بارگذاری کنید؛ پردازش در پس‌زمینه ادامه پیدا می‌کند.<br>متن اولیه را همین‌جا بخوانید، دریافت کنید و برای بازبینی آماده نگه دارید.</p></div>', unsafe_allow_html=True)
with st.sidebar:
    st.subheader("🎙️ گفتار")
    st.caption("کارگاه تبدیل صوت به متن")
    st.divider()
    st.markdown("**۱. بارگذاری صوت**\n\n**۲. پردازش در گیت‌هاب**\n\n**۳. دریافت متن اولیه**\n\n**۴. بازبینی جداگانه**")
    st.divider()
    st.caption("فارسی و عربی · فایل تا ۵۰۰ مگابایت")
    st.caption("برای جلسه‌های فارسی دارای آیات، زبان فارسی را انتخاب کنید.")
    if st.button("خروج"):
        st.session_state.clear()
        st.rerun()

upload_tab, result_tab, review_tab = st.tabs(["صوت جدید", "کارها و متن‌ها", "آماده‌سازی بازبینی"])
with upload_tab:
    st.markdown('<div class="step">صوت ← ریلیز rag_finance ← پردازش مستقل ← متن اولیه</div>', unsafe_allow_html=True)
    st.subheader("یک گفتار تازه اضافه کنید")
    title = st.text_input("عنوان جلسه", placeholder="مثلاً: نگاه قرآنی به رسالت انسانی — جلسه سوم", max_chars=160)
    language = st.selectbox("زبان اصلی گفتار", ["fa", "ar"], format_func=lambda x: {"fa": "فارسی، همراه با نقل‌قول عربی", "ar": "عربی"}[x])
    uploaded = st.file_uploader("فایل صوتی", type=sorted(x[1:] for x in AUDIO_TYPES),
                                help="MP3، M4A، WAV و دیگر قالب‌های صوتی؛ حداکثر ۵۰۰ مگابایت.")
    st.caption("فایل و متن در ریلیز و شاخهٔ همین مخزن ذخیره می‌شوند؛ اگر مخزن عمومی باشد، آن‌ها هم عمومی خواهند بود.")
    consent = st.checkbox("ذخیرهٔ این صوت و متن آن در مخزن و ریلیز را تأیید می‌کنم.")
    if st.button("بارگذاری و شروع تبدیل", type="primary", disabled=not uploaded or not consent):
        gh = client()
        try:
            data = uploaded.getbuffer()
            fingerprint = hashlib.sha256(data).hexdigest() + language + title
            submissions = st.session_state.setdefault("submissions", {})
            slot = submissions.setdefault(fingerprint, {"id": uuid.uuid4().hex})
            with st.status("در حال ثبت صوت…", expanded=True) as progress:
                st.write("انتقال امن به ریلیز")
                asset_id = gh.upload(slot["id"], uploaded.name, data)
                if "job" not in slot:
                    slot["job"] = make_job(slot["id"], uploaded.name, data, asset_id, title, language)
                st.write("ثبت درخواست پردازش مستقل")
                gh.enqueue(slot["job"])
                progress.update(label="درخواست ثبت شد؛ پردازش در گیت‌هاب شروع می‌شود.", state="complete", expanded=False)
            st.session_state.selected_job = slot["id"]
            st.query_params["job"] = slot["id"]
            st.success("می‌توانید صفحه را ببندید؛ درخواست و صوت در مخزن باقی می‌مانند.")
            st.code(slot["id"], language=None)
            st.info("برای پیگیری، تب «کارها و متن‌ها» را باز کنید. شناسه در نشانی همین صفحه هم ثبت شد.")
        except (PortalError, ValueError) as exc:
            st.error(str(exc))
        finally:
            gh.close()

with result_tab:
    st.subheader("متن‌ها، به ترتیب ثبت")
    st.caption("وضعیت هر ۲۰ ثانیه تازه می‌شود. زمان باقیمانده یا درصد ساختگی نمایش داده نمی‌شود.")

    @st.fragment(run_every="20s")
    def dashboard():
        gh = client()
        try:
            ids = gh.jobs()
            if not ids:
                st.info("هنوز صوتی در این کارگاه ثبت نشده است.")
                return
            # Sort the newest 50 by durable metadata, rather than random UUID order.
            jobs = [gh.job(i) for i in ids]
            jobs.sort(key=lambda j: j["created_at"], reverse=True)
            by_id = {j["id"]: j for j in jobs}
            selected = st.query_params.get("job") or st.session_state.get("selected_job")
            order = [j["id"] for j in jobs]
            index = order.index(selected) if selected in order else 0
            job_id = st.selectbox("انتخاب جلسه", order, index=index,
                format_func=lambda i: by_id[i]["title"] + " · " + by_id[i]["created_at"][:16], key="job_picker")
            job = by_id[job_id]
            st.session_state.selected_job = job_id
            state = gh.status(job)
            st.markdown("### " + LABELS.get(state["state"], state["state"]))
            cols = st.columns(3)
            cols[0].metric("حجم صوت", f"{job['size'] / 1024**2:.1f} MB")
            cols[1].metric("زبان", "فارسی" if job["language"] == "fa" else "عربی")
            cols[2].metric("مرحلهٔ بازبینی", "در انتظار بررسی")
            st.caption(f"شناسه: {job_id} · ثبت: {job['created_at'][:19]}")
            if state.get("updated_at"):
                st.caption("آخرین تغییر وضعیت: " + state["updated_at"][:19])
            if state.get("run_url"):
                st.link_button("مشاهدهٔ جزئیات اجرا", state["run_url"])
            if state["state"] in {"failed", "failure", "cancelled", "timed_out"}:
                st.error("کار کامل نشده است. جزئیات اجرا را بررسی کنید؛ متن ناقص به‌عنوان خروجی کامل ارائه نمی‌شود.")
                if st.button("تلاش دوباره با همان صوت", key="retry-" + job_id):
                    new = dict(job, id=uuid.uuid4().hex, created_at=__import__("backend").now(), retry_of=job_id)
                    gh.enqueue(new)
                    st.query_params["job"] = new["id"]
                    st.rerun()
            if state["state"] == "completed":
                st.info("این خروجی، متن ماشینی اولیه است. صحت آیات، نام‌ها و بخش‌های مبهم هنوز نیازمند بازبینی است.")
                root = f"outputs/audio-portal/{job_id}"
                draft = gh.read(root + "/transcript.txt")
                if draft:
                    st.text_area("متن کامل اولیه", draft["data"].decode("utf-8"), height=500, disabled=True)
                for filename, label in [("transcript.md", "دانلود Markdown"), ("transcript.txt", "دانلود متن"),
                                         ("transcript.timestamped.md", "دانلود متن زمان‌دار")]:
                    file = gh.read(root + "/" + filename)
                    if file:
                        st.download_button(label, file["data"], file_name=f"{job_id}-{filename}", key=filename)
        except (PortalError, ValueError, KeyError):
            st.error("دریافت وضعیت فعلاً ممکن نیست. چند لحظه بعد دوباره بررسی کنید.")
        finally:
            gh.close()
    dashboard()

with review_tab:
    st.subheader("بازبینی، با حفظ نسخهٔ اولیه")
    st.write("متن اولیه و متن زمان‌دار در کنار هم به بستهٔ بازبینی تبدیل می‌شوند. اصلاحات باید در نسخه‌ای جدا انجام شوند؛ برای آیات و عبارت‌های مبهم، صوت مرجع اصلی است.")
    st.caption("در این نسخه بازبینی خودکار اجرا نمی‌شود و متن ماشینی با عنوان «بازبینی‌شده» نمایش داده نمی‌شود.")
    selected = st.session_state.get("selected_job")
    if selected and st.button("آماده‌سازی بستهٔ بازبینی"):
        gh = client()
        try:
            job = gh.job(selected)
            if gh.status(job)["state"] != "completed":
                st.warning("ابتدا باید تبدیل صوت کامل شود.")
            else:
                bundle = io.BytesIO()
                with zipfile.ZipFile(bundle, "w", zipfile.ZIP_DEFLATED) as archive:
                    archive.writestr("source.json", json.dumps(job, ensure_ascii=False, indent=2))
                    for name in ["transcript.md", "transcript.timestamped.md", "transcript.txt", "transcript.raw.json"]:
                        data = gh.read(f"outputs/audio-portal/{selected}/{name}")
                        if data:
                            archive.writestr(name, data["data"])
                    archive.writestr("review-instructions.md", "# دستور بازبینی\nمتن کامل را با صوت تطبیق بده؛ حذف و خلاصه نکن. صورت عربی آیات را با منبع معتبر کنترل کن. عبارت نامطمئن را علامت بزن و حدس را قطعی ننویس. متن اولیه را نگه دار و اصلاحات را در transcript.reviewed.md با فهرست تغییرات و زمان بخش‌ها ثبت کن. بدون شنیدن صوت، ادعای تطبیق کامل نکن.\n")
                st.download_button("دانلود بستهٔ بازبینی", bundle.getvalue(), file_name=f"review-{selected}.zip", mime="application/zip")
        except (PortalError, ValueError):
            st.error("ساخت بسته ممکن نشد؛ وضعیت کار را بررسی کنید.")
        finally:
            gh.close()
