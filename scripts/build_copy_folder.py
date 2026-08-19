#!/usr/bin/env python3
"""Build a clean Persian Markdown-only copy/ directory from canonical transcripts.

The copy directory is intentionally presentation-oriented: one readable Markdown
file per requested program/episode, with provenance and duration in a fixed header.
Review-final Markdown is preferred when available; otherwise the canonical
Delivery Markdown is used. Review packages/drafts are never copied.
"""

from __future__ import annotations

import argparse
import csv
import json
import re
import shutil
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
OUTPUTS = ROOT / "outputs"
COPY = ROOT / "copy"

CHEHELSTOUN_PROGRAM_PAGE = "http://radio.iranseda.ir/Program/?VALID=TRUE&ch=57&m=090513"
CHEHELSTOUN_ARCHIVE_PAGE = "https://github.com/Shahbazi-Amir/vid_pipeline/releases/tag/chehelstoun-archive-v1"
KETAB_BAZ_SOURCE_PAGE = "https://rss.castbox.fm/everest/db2dc0b37407484e86691781e9f82d03.xml"
KETAB_BAZ_ARCHIVE_PAGE = "https://github.com/Shahbazi-Amir/vid_pipeline/releases/tag/ketab-baz-s05e68-komeil-roudi"
FINUP_PROGRAM_PAGE = "https://youtu.be/bpelPbGcBMc"
FINUP_ARCHIVE_PAGE = "https://github.com/Shahbazi-Amir/vid_pipeline/releases/tag/finup21-komeil-roudi-financial-literacy"
MIZAN_ARCHIVE_PAGE = CHEHELSTOUN_ARCHIVE_PAGE
BANK_ARCHIVE_PAGE = "https://github.com/Shahbazi-Amir/vid_pipeline/releases/tag/bankmellatt"


def load_json(path: Path) -> dict[str, Any]:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError, UnicodeDecodeError):
        return {}


def clean_text(value: Any) -> str:
    text = str(value or "").strip()
    return re.sub(r"\s+", " ", text)


def transcript_for(root: Path) -> tuple[Path | None, str]:
    candidates = [
        (root / "final" / "transcript.final.md", "نهایی بازبینی‌شده"),
        (root / "delivery" / "transcript.md", "نسخه تحویلی نهایی خط پردازش"),
    ]
    for path, label in candidates:
        if path.is_file() and path.stat().st_size > 0:
            return path, label
    return None, ""


def source_data(root: Path) -> dict[str, Any]:
    return load_json(root / "source.json")


def metadata(root: Path) -> dict[str, Any]:
    return load_json(root / "metadata.json")


def duration_seconds(root: Path) -> float | None:
    src = source_data(root)
    media = src.get("media") if isinstance(src.get("media"), dict) else {}
    raw = media.get("duration_seconds")
    if raw is None:
        result = load_json(root / "result.json")
        for candidate in (
            result.get("duration_seconds"),
            (result.get("media") or {}).get("duration_seconds") if isinstance(result.get("media"), dict) else None,
        ):
            if candidate is not None:
                raw = candidate
                break
    try:
        return float(raw) if raw is not None else None
    except (TypeError, ValueError):
        return None


def format_duration(seconds: float | None) -> str:
    if seconds is None or seconds < 0:
        return "نامشخص"
    total = int(round(seconds))
    h, rem = divmod(total, 3600)
    m, s = divmod(rem, 60)
    minutes = total / 60
    return f"{h:02d}:{m:02d}:{s:02d} ({minutes:.1f} دقیقه)"


def provenance(root: Path) -> tuple[str, str, str]:
    """Return (source_page_url, original_download_url, archive_or_source_url)."""
    src = source_data(root)
    prov = src.get("provenance") if isinstance(src.get("provenance"), dict) else {}
    source_page = clean_text(prov.get("source_page_url") or src.get("source_page_url"))
    original = clean_text(prov.get("original_download_url") or src.get("original_download_url"))
    archive = clean_text(prov.get("archive_url") or src.get("archive_url") or src.get("source_url"))
    return source_page, original, archive


def markdown_link(label: str, url: str) -> str:
    return f"[{label}]({url})" if url else "ثبت نشده"


def strip_existing_frontmatter(text: str) -> str:
    # Keep the transcript intact except for accidental leading blank space.
    return text.lstrip("\ufeff\n\r")


def write_copy(
    *,
    filename: str,
    program: str,
    episode: str,
    root: Path,
    title: str,
    description: str,
    program_page: str,
    source_audio_url: str = "",
    archive_page: str = "",
) -> bool:
    transcript, version = transcript_for(root)
    if transcript is None:
        return False

    source_page, original, archived_source = provenance(root)
    effective_page = source_page or program_page
    effective_audio = source_audio_url or original or archived_source
    effective_archive = archive_page or archived_source

    body = strip_existing_frontmatter(transcript.read_text(encoding="utf-8"))
    duration = format_duration(duration_seconds(root))
    title = clean_text(title) or f"{program} {episode}".strip()
    description = clean_text(description) or title

    header = [
        f"# {program}{(' ' + episode) if episode else ''}",
        "",
        f"- **برنامه:** {program}",
        f"- **قسمت:** {episode or 'تک‌قسمت'}",
        f"- **عنوان/موضوع:** {title}",
        f"- **توضیحات:** {description}",
        f"- **مدت‌زمان کل:** {duration}",
        f"- **وضعیت متن:** {version}",
        f"- **صفحه/فید منبع:** {markdown_link('مشاهده منبع', effective_page)}",
        f"- **لینک فایل منبع:** {markdown_link('فایل صوتی', effective_audio)}",
        f"- **آرشیو پروژه:** {markdown_link('GitHub Release', effective_archive)}",
        "",
        "---",
        "",
    ]
    (COPY / filename).write_text("\n".join(header) + body.rstrip() + "\n", encoding="utf-8")
    return True


def read_chehelstoun_manifest(path: Path | None) -> dict[int, dict[str, str]]:
    if path is None or not path.is_file():
        return {}
    rows: dict[int, dict[str, str]] = {}
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        for row in csv.DictReader(handle):
            try:
                rows[int(row.get("episode") or "")] = {k: clean_text(v) for k, v in row.items()}
            except ValueError:
                continue
    return rows


def first_completed_child(parent: Path) -> Path | None:
    if not parent.is_dir():
        return None
    for child in sorted((p for p in parent.iterdir() if p.is_dir()), key=lambda p: p.name):
        if transcript_for(child)[0] is not None:
            return child
    return None


def build(manifest_path: Path | None) -> dict[str, Any]:
    if COPY.exists():
        shutil.rmtree(COPY)
    COPY.mkdir(parents=True, exist_ok=True)

    manifest = read_chehelstoun_manifest(manifest_path)
    created: list[str] = []
    missing: list[str] = []

    # Chehelstoun 1..38 — complete series requested by the user.
    for ep in range(1, 39):
        root = OUTPUTS / "chehelstoun" / f"{ep:02d}"
        row = manifest.get(ep, {})
        meta = metadata(root)
        title = row.get("title") or clean_text(meta.get("title")) or f"چهلستون - قسمت {ep}"
        source_audio = row.get("source_url", "")
        description = f"قسمت {ep} از مجموعه رادیویی چهلستون؛ {title}."
        name = f"چهلستون {ep}.md"
        if write_copy(
            filename=name,
            program="چهلستون",
            episode=str(ep),
            root=root,
            title=title,
            description=description,
            program_page=CHEHELSTOUN_PROGRAM_PAGE,
            source_audio_url=source_audio,
            archive_page=CHEHELSTOUN_ARCHIVE_PAGE,
        ):
            created.append(name)
        else:
            missing.append(name)

    # Ketab Baz — Komeil Roudi episode.
    root = OUTPUTS / "ketab-baz" / "01"
    name = "کتاب باز.md"
    if write_copy(
        filename=name,
        program="کتاب باز",
        episode="فصل ۵ - دکتر کمیل رودی",
        root=root,
        title="کتاب باز - دکتر کمیل رودی",
        description="گفت‌وگوی سروش صحت با دکتر کمیل رودی در برنامه کتاب باز.",
        program_page=KETAB_BAZ_SOURCE_PAGE,
        archive_page=KETAB_BAZ_ARCHIVE_PAGE,
    ):
        created.append(name)
    else:
        missing.append(name)

    # Mizan.
    root = OUTPUTS / "mizan" / "01"
    name = "میزان.md"
    if write_copy(
        filename=name,
        program="میزان",
        episode="1",
        root=root,
        title="میزان",
        description="فایل برنامه میزانِ آرشیوشده و پردازش‌شده در پروژه.",
        program_page=MIZAN_ARCHIVE_PAGE,
        archive_page=MIZAN_ARCHIVE_PAGE,
    ):
        created.append(name)
    else:
        missing.append(name)

    # Finup (user-facing name requested: فناپ).
    finup_root = first_completed_child(OUTPUTS / "finup")
    name = "فناپ.md"
    if finup_root and write_copy(
        filename=name,
        program="فناپ",
        episode="رویداد ۲۱",
        root=finup_root,
        title="سواد مالی چه هست و چه نیست؟ - کمیل رودی",
        description="ارائه دکتر کمیل رودی در رویداد ۲۱ فیناپ درباره تعریف و مرزهای سواد مالی.",
        program_page=FINUP_PROGRAM_PAGE,
        archive_page=FINUP_ARCHIVE_PAGE,
    ):
        created.append(name)
    else:
        missing.append(name)

    # Sherakat: support several historical/likely directory spellings without
    # inventing content when it has not yet reached outputs.
    sherakat_root = None
    for dirname in ("sherakat", "sharakat", "sharekat", "partnership"):
        candidate = OUTPUTS / dirname
        if transcript_for(candidate)[0] is not None:
            sherakat_root = candidate
            break
        child = first_completed_child(candidate)
        if child:
            sherakat_root = child
            break
    name = "شراکت.md"
    if sherakat_root and write_copy(
        filename=name,
        program="شراکت",
        episode="1",
        root=sherakat_root,
        title="شراکت",
        description="فایل برنامه شراکتِ آرشیوشده و پردازش‌شده در پروژه.",
        program_page="",
    ):
        created.append(name)
    else:
        missing.append(name)

    # Bank Mellat: accept 1..11 as they become available. At present only
    # genuinely generated outputs are copied; no placeholder transcript is made.
    for ep in range(1, 12):
        root = OUTPUTS / "bankmellatt" / str(ep)
        name = f"بانک ملت {ep}.md"
        if write_copy(
            filename=name,
            program="بانک ملت",
            episode=str(ep),
            root=root,
            title=f"بانک ملت - قسمت {ep}",
            description=f"قسمت {ep} از مجموعه بانک ملت؛ فایل آرشیوشده و پردازش‌شده در پروژه.",
            program_page=BANK_ARCHIVE_PAGE,
            archive_page=BANK_ARCHIVE_PAGE,
        ):
            created.append(name)
        elif ep <= 8:
            missing.append(name)

    non_md = [str(p.relative_to(COPY)) for p in COPY.rglob("*") if p.is_file() and p.suffix.lower() != ".md"]
    if non_md:
        raise SystemExit(f"copy/ contains non-Markdown files: {non_md}")

    summary = {"created_count": len(created), "created": created, "missing_requested": missing}
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return summary


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--chehelstoun-manifest", type=Path, default=None)
    args = parser.parse_args()
    build(args.chehelstoun_manifest)


if __name__ == "__main__":
    main()
