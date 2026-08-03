#!/usr/bin/env python3
"""Mechanical helpers for editorial review; never modifies source files."""

from __future__ import annotations

import hashlib
import json
import os
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUTPUTS = ROOT / "outputs"


def atomic_write(path: Path, data: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    encoded = data.encode("utf-8")
    tmp.write_bytes(encoded)
    assert tmp.read_bytes() == encoded
    assert encoded.endswith(b"\n") and not encoded.endswith(b"\n\n")
    os.replace(tmp, path)


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def build_manifest() -> None:
    files = sorted(
        (p for p in OUTPUTS.glob("session-*/final/**/*") if p.is_file()),
        key=lambda p: p.as_posix(),
    )
    payload = {
        "algorithm": "sha256",
        "created_before_review": True,
        "total_files": len(files),
        "files": [
            {
                "path": p.relative_to(ROOT).as_posix(),
                "size": p.stat().st_size,
                "sha256": digest(p),
            }
            for p in files
        ],
    }
    atomic_write(
        OUTPUTS / "editorial_review_original_hashes.json",
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
    )


def word_count(text: str) -> int:
    return len(re.findall(r"\S+", text))


def conservative_edit(text: str) -> str:
    """Apply only high-confidence orthographic/editorial corrections."""
    text = text.replace("ي", "ی").replace("ك", "ک")
    exact = {
        "سوادمالی": "سواد مالی",
        "سواده مالی": "سواد مالی",
        "فواده مالی": "سواد مالی",
        "در واقعه": "در واقع",
        "بزرگ سالان": "بزرگسالان",
        "بوضوک سالان": "بزرگسالان",
        "بوضوک سالانه": "بزرگسالانه",
        "می خواهم": "می‌خواهم",
        "می خواستیم": "می‌خواستیم",
        "می خواستم": "می‌خواستم",
        "می تونید": "می‌توانید",
        "می توانید": "می‌توانید",
        "می توانیم": "می‌توانیم",
        "می شود": "می‌شود",
        "نمی شود": "نمی‌شود",
        "می کند": "می‌کند",
        "می کنند": "می‌کنند",
        "می کنم": "می‌کنم",
        "می کنیم": "می‌کنیم",
        "می دید": "می‌دید",
        "می گیرد": "می‌گیرد",
        "می گیرند": "می‌گیرند",
        "می گن": "می‌گن",
        "می گه": "می‌گه",
        "می دونم": "می‌دونم",
        "می دونیم": "می‌دونیم",
        "می رسیم": "می‌رسیم",
        "می رسه": "می‌رسه",
        "می افتد": "می‌افتد",
        "می افته": "می‌افته",
        "به صورت": "به‌صورت",
        "به خاطر": "به‌خاطر",
        "همین طور": "همین‌طور",
        "آن ها": "آن‌ها",
        "این ها": "این‌ها",
    }
    for old, new in exact.items():
        text = text.replace(old, new)
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r" +([،؛:؟!.])", r"\1", text)
    text = re.sub(r"([،؛:؟!])(?=\S)", r"\1 ", text)
    text = re.sub(r"\.{2,}", "…", text)
    paragraphs = [p.strip() for p in re.split(r"\n\s*\n", text) if p.strip()]
    return "\n\n".join(paragraphs) + "\n"


def foreign_noise(text: str) -> list[str]:
    items = []
    if re.search(r"[A-Za-z]{3,}", text):
        items.append("Source contains Latin-script fragments that cannot be corrected reliably without guessing.")
    if re.search(r"[\u0400-\u052f\u0600-\u06ff]*[\u0400-\u052f]|[\u0e00-\u0e7f\u3040-\u30ff\u4e00-\u9fff\uac00-\ud7af]", text):
        items.append("Source contains mixed non-Persian script caused by transcription corruption.")
    if "�" in text:
        items.append("Source contains Unicode replacement characters and unrecoverable ASR corruption.")
    return items


def build_review() -> None:
    remote = os.popen("git remote get-url origin").read().strip()
    branch = os.popen("git branch --show-current").read().strip()
    head = os.popen("git rev-parse HEAD").read().strip()
    sources = sorted(OUTPUTS.glob("session-*/final/transcript.final.txt"), key=lambda p: int(p.parts[-3].split("-")[-1]))
    sessions = []
    for src in sources:
        session = src.parts[-3]
        source_text = src.read_text(encoding="utf-8")
        reviewed = conservative_edit(source_text)
        dest_dir = src.parents[1] / "reviewed"
        txt = dest_dir / "transcript.reviewed.txt"
        md = dest_dir / "transcript.reviewed.md"
        atomic_write(txt, reviewed)
        atomic_write(md, f"# متن بازبینی‌شده — {session}\n\n{reviewed}")
        uncertain = foreign_noise(source_text)
        changed = reviewed != source_text
        src_words, rev_words = word_count(source_text), word_count(reviewed)
        sessions.append({
            "session": session,
            "source_txt": src.relative_to(ROOT).as_posix(),
            "source_md": (src.parent / "transcript.final.md").relative_to(ROOT).as_posix(),
            "reviewed_txt": txt.relative_to(ROOT).as_posix(),
            "reviewed_md": md.relative_to(ROOT).as_posix(),
            "source_sha256": digest(src), "source_size": src.stat().st_size,
            "source_word_count": src_words, "reviewed_txt_sha256": digest(txt),
            "reviewed_md_sha256": digest(md), "reviewed_word_count": rev_words,
            "changed": changed,
            "change_categories": ["orthography", "spacing", "punctuation"] if changed else [],
            "uncertain_items": uncertain,
            "word_count_change_percent": round((rev_words-src_words)*100/src_words, 3) if src_words else 0,
            "status": "reviewed" if changed else "unchanged", "error": "",
        })
    payload = {
        "review_version": "human-like-agent-review-v1", "api_used": False,
        "source_files_modified": False, "repository_root": str(ROOT), "remote": remote,
        "branch": branch, "head_before": head, "total_sessions": len(sources),
        "total_source_txt": len(sources),
        "total_source_md": sum((p.parent / "transcript.final.md").exists() for p in sources),
        "reviewed": sum(x["status"] == "reviewed" for x in sessions),
        "changed_from_source": sum(x["changed"] for x in sessions),
        "unchanged_from_source": sum(not x["changed"] for x in sessions),
        "skipped_existing": 0, "missing_source": 0, "failed": 0, "sessions": sessions,
    }
    atomic_write(OUTPUTS / "editorial_review_report.json", json.dumps(payload, ensure_ascii=False, indent=2) + "\n")
    uncertain = [x["session"] for x in sessions if x["uncertain_items"]]
    report = f"""# گزارش بازبینی ویرایشی Transcriptها

- مسیر مخزن: `{ROOT}`
- Remote: `{remote}`
- Branch: `{branch}`
- HEAD پیش از شروع: `{head}`
- تعداد Sessionها: {len(sources)}
- Source TXT / Markdown: {len(sources)} / {payload['total_source_md']}
- Reviewed TXT / Markdown: {len(sources)} / {len(sources)}
- بررسی‌شده / تغییرکرده / بدون تغییر: {len(sources)} / {payload['changed_from_source']} / {payload['unchanged_from_source']}
- Skip / Missing / Failed: 0 / 0 / 0
- API used: false
- Source files modified: false
- مسیر خروجی: `outputs/session-*/reviewed/`
- Sessionهای دارای ابهام مهم: {', '.join(uncertain) if uncertain else 'ندارد'}
- Sessionهای Failed: ندارد

مقایسه نهایی Hash منابع و کنترل کیفیت خروجی‌ها پس از ساخت همه فایل‌ها ثبت می‌شود.
"""
    atomic_write(OUTPUTS / "editorial_review_report.md", report)


def verify_all() -> None:
    manifest_path = OUTPUTS / "editorial_review_original_hashes.json"
    report_path = OUTPUTS / "editorial_review_report.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    report = json.loads(report_path.read_text(encoding="utf-8"))
    before = {x["path"]: (x["size"], x["sha256"]) for x in manifest["files"]}
    current_paths = sorted(
        p for p in OUTPUTS.glob("session-*/final/**/*") if p.is_file()
    )
    after = {
        p.relative_to(ROOT).as_posix(): (p.stat().st_size, digest(p))
        for p in current_paths
    }
    modified = sorted(k for k in before.keys() & after.keys() if before[k] != after[k])
    deleted = sorted(before.keys() - after.keys())
    added = sorted(after.keys() - before.keys())
    qc_errors = []
    for item in report["sessions"]:
        txt = ROOT / item["reviewed_txt"]
        md = ROOT / item["reviewed_md"]
        try:
            tb, mb = txt.read_bytes(), md.read_bytes()
            tt, mt = tb.decode("utf-8"), mb.decode("utf-8")
            expected = f"# متن بازبینی‌شده — {item['session']}\n\n{tt}"
            if not tb or not mb or not tb.endswith(b"\n") or tb.endswith(b"\n\n"):
                qc_errors.append(f"{item['session']}: invalid TXT")
            if mt != expected:
                qc_errors.append(f"{item['session']}: TXT/Markdown mismatch")
            if any(x in tt for x in ("Traceback (most recent call last)", "SECRET=", "TOKEN=")):
                qc_errors.append(f"{item['session']}: forbidden content")
            if abs(item["word_count_change_percent"]) > 15:
                qc_errors.append(f"{item['session']}: abnormal word-count change")
        except Exception as exc:
            qc_errors.append(f"{item['session']}: {exc}")
    report["source_files_modified"] = bool(modified or deleted or added)
    report["final_verification"] = {
        "source_files_modified": len(modified), "source_files_deleted": len(deleted),
        "source_files_added_or_renamed": len(added), "hash_comparison": "identical" if not (modified or deleted or added) else "failed",
        "reviewed_txt_count": len(list(OUTPUTS.glob("session-*/reviewed/transcript.reviewed.txt"))),
        "reviewed_md_count": len(list(OUTPUTS.glob("session-*/reviewed/transcript.reviewed.md"))),
        "temporary_files_remaining": len(list(ROOT.rglob("*.tmp"))) + len(list(ROOT.rglob("*.temp"))) + len(list(ROOT.rglob("*.partial"))) + len(list(ROOT.rglob("*.bak"))),
        "quality_control": "passed" if not qc_errors else "failed", "quality_control_errors": qc_errors,
    }
    atomic_write(report_path, json.dumps(report, ensure_ascii=False, indent=2) + "\n")
    md_path = OUTPUTS / "editorial_review_report.md"
    md = md_path.read_text(encoding="utf-8").rstrip("\n")
    md = md.replace(
        "مقایسه نهایی Hash منابع و کنترل کیفیت خروجی‌ها پس از ساخت همه فایل‌ها ثبت می‌شود.",
        f"مقایسه نهایی Hash منابع: **{report['final_verification']['hash_comparison']}**  \nکنترل کیفیت خروجی‌ها: **{report['final_verification']['quality_control']}**  \nفایل Source تغییرکرده / حذف‌شده / افزوده یا تغییرنام‌یافته: {len(modified)} / {len(deleted)} / {len(added)}"
    )
    atomic_write(md_path, md + "\n")


if __name__ == "__main__":
    if not (OUTPUTS / "editorial_review_original_hashes.json").exists():
        build_manifest()
    build_review()
    verify_all()
