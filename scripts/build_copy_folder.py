#!/usr/bin/env python3
"""Build a Markdown-only presentation copy from repository outputs.

Rules:
- one readable .md file per requested item;
- prefer reviewed/finalized transcript when available;
- never expose repository/release URLs as source links;
- show only a real external internet source page when one is known;
- keep provenance/audit JSON in internal output trees, not in copy/.
"""
from __future__ import annotations

import json
import re
import shutil
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
OUTPUTS = ROOT / "outputs"
COPY = ROOT / "copy"

# Public internet pages only. Empty means: no reliable original/public page verified yet.
CHEHELSTOUN_SOURCE_PAGE = "https://radio.iranseda.ir/Program/?VALID=TRUE&ch=57&m=090513"
KETAB_BAZ_SOURCE_PAGE = "https://taaghche.com/audiobook/255204"
FINUP_SOURCE_PAGE = "https://youtu.be/bpelPbGcBMc"
MIZAN_SOURCE_PAGE = ""
SHERAKAT_SOURCE_PAGE = ""
BANK_MELLAT_SOURCE_PAGE = ""


def load_json(path: Path) -> dict[str, Any]:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError, UnicodeDecodeError):
        return {}


def clean_text(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "").strip())


def finalized_path_for(root: Path) -> Path | None:
    try:
        rel = root.relative_to(OUTPUTS)
    except ValueError:
        return None
    if not rel.parts or rel.parts[0] in {"finalized", "review-ready"}:
        return None
    candidate = OUTPUTS / "finalized" / rel / "transcript.md"
    return candidate if candidate.is_file() and candidate.stat().st_size > 0 else None


def transcript_for(root: Path) -> tuple[Path | None, str]:
    candidates: list[tuple[Path, str]] = []
    canonical_final = finalized_path_for(root)
    if canonical_final is not None:
        candidates.append((canonical_final, "نهایی بازبینی‌شده"))
    candidates.extend([
        (root / "final" / "transcript.final.md", "نهایی بازبینی‌شده"),
        (root / "delivery" / "transcript.md", "نسخه تحویلی خط پردازش"),
    ])
    for path, label in candidates:
        if path.is_file() and path.stat().st_size > 0:
            return path, label
    return None, ""


def source_data(root: Path) -> dict[str, Any]:
    return load_json(root / "source.json")


def duration_seconds(root: Path) -> float | None:
    src = source_data(root)
    media = src.get("media") if isinstance(src.get("media"), dict) else {}
    raw = media.get("duration_seconds")
    if raw is None:
        result = load_json(root / "result.json")
        raw = result.get("duration_seconds")
        if raw is None and isinstance(result.get("media"), dict):
            raw = result["media"].get("duration_seconds")
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
    return f"{h:02d}:{m:02d}:{s:02d} ({total / 60:.1f} دقیقه)"


def markdown_link(url: str) -> str:
    return f"[مشاهده منبع اصلی]({url})" if url else "ثبت نشده"


def clean_body(text: str) -> str:
    """Remove internal GitHub/release provenance from the readable copy body."""
    kept: list[str] = []
    for line in text.lstrip("\ufeff\n\r").splitlines():
        lowered = line.lower()
        if "github.com/shahbazi-amir/vid_pipeline" in lowered:
            continue
        if line.strip() in {"## منبع فایل", "---"} and not kept:
            continue
        if line.strip().startswith("- نسخه آرشیوی:"):
            continue
        if line.strip().startswith("**منبع:**"):
            continue
        kept.append(line)
    body = "\n".join(kept).strip()
    body = re.sub(r"\n{4,}", "\n\n\n", body)
    return body + "\n"


def old_copy_title(filename: str) -> str:
    path = COPY / filename
    if not path.is_file():
        return ""
    try:
        for line in path.read_text(encoding="utf-8").splitlines()[:20]:
            if line.startswith("- **عنوان/موضوع:**"):
                return clean_text(line.split(":**", 1)[-1])
    except UnicodeDecodeError:
        pass
    return ""


def write_copy(*, filename: str, program: str, episode: str, root: Path,
               title: str, description: str, source_page: str) -> bool:
    transcript, version = transcript_for(root)
    if transcript is None:
        return False
    title = clean_text(title) or f"{program} {episode}".strip()
    description = clean_text(description) or title
    body = clean_body(transcript.read_text(encoding="utf-8"))
    header = [
        f"# {program}{(' ' + episode) if episode else ''}",
        "",
        f"- **برنامه:** {program}",
        f"- **قسمت:** {episode or 'تک‌قسمت'}",
        f"- **عنوان/موضوع:** {title}",
        f"- **توضیحات:** {description}",
        f"- **مدت‌زمان کل:** {format_duration(duration_seconds(root))}",
        f"- **وضعیت متن:** {version}",
        f"- **لینک منبع اصلی:** {markdown_link(source_page)}",
        "",
        "---",
        "",
    ]
    (COPY / filename).write_text("\n".join(header) + body, encoding="utf-8")
    return True


def first_completed_child(parent: Path) -> Path | None:
    if not parent.is_dir():
        return None
    for child in sorted((p for p in parent.iterdir() if p.is_dir()), key=lambda p: p.name):
        if transcript_for(child)[0] is not None:
            return child
    return None


def build() -> dict[str, Any]:
    # Preserve currently known human-friendly titles before replacing copy/.
    prior_titles = {f"چهلستون {ep}.md": old_copy_title(f"چهلستون {ep}.md") for ep in range(1, 39)}
    if COPY.exists():
        shutil.rmtree(COPY)
    COPY.mkdir(parents=True, exist_ok=True)

    created: list[str] = []
    missing: list[str] = []

    for ep in range(1, 39):
        root = OUTPUTS / "chehelstoun" / f"{ep:02d}"
        name = f"چهلستون {ep}.md"
        title = prior_titles.get(name) or f"چهلستون - قسمت {ep}"
        if write_copy(
            filename=name, program="چهلستون", episode=str(ep), root=root,
            title=title,
            description=f"قسمت {ep} از مجموعه رادیویی چهلستون درباره سواد مالی و اقتصاد خانواده.",
            source_page=CHEHELSTOUN_SOURCE_PAGE,
        ):
            created.append(name)
        else:
            missing.append(name)

    root = OUTPUTS / "ketab-baz" / "01"
    name = "کتاب باز.md"
    if write_copy(
        filename=name, program="کتاب باز", episode="فصل ۵ - قسمت ۶۸", root=root,
        title="کتاب باز - دکتر کمیل رودی",
        description="گفت‌وگوی سروش صحت با دکتر کمیل رودی درباره سواد مالی در برنامه کتاب باز.",
        source_page=KETAB_BAZ_SOURCE_PAGE,
    ):
        created.append(name)
    else:
        missing.append(name)

    root = OUTPUTS / "mizan" / "01"
    name = "میزان.md"
    if write_copy(
        filename=name, program="میزان", episode="1", root=root,
        title="میزان",
        description="متن برنامه میزانِ پردازش‌شده در پروژه.",
        source_page=MIZAN_SOURCE_PAGE,
    ):
        created.append(name)
    else:
        missing.append(name)

    finup_root = first_completed_child(OUTPUTS / "finup")
    name = "فناپ.md"
    if finup_root and write_copy(
        filename=name, program="فیناپ", episode="رویداد ۲۱", root=finup_root,
        title="سواد مالی چه هست و چه نیست؟ - کمیل رودی",
        description="ارائه دکتر کمیل رودی در بیست‌ویکمین رویداد فیناپ درباره تعریف و مرزهای سواد مالی.",
        source_page=FINUP_SOURCE_PAGE,
    ):
        created.append(name)
    else:
        missing.append(name)

    sherakat_root = OUTPUTS / "voice-260817-165035" / "01"
    name = "شراکت.md"
    if write_copy(
        filename=name, program="شراکت", episode="1", root=sherakat_root,
        title="شراکت",
        description="متن فایل صوتی شراکتِ اضافه‌شده به مجموعه داده پروژه.",
        source_page=SHERAKAT_SOURCE_PAGE,
    ):
        created.append(name)
    else:
        missing.append(name)

    for ep in range(1, 12):
        root = OUTPUTS / "bankmellatt" / str(ep)
        name = f"بانک ملت {ep}.md"
        if write_copy(
            filename=name, program="بانک ملت", episode=str(ep), root=root,
            title=f"بانک ملت - قسمت {ep}",
            description=f"قسمت {ep} از مجموعه آموزشی بانک ملت؛ متن پردازش‌شده فایل موجود.",
            source_page=BANK_MELLAT_SOURCE_PAGE,
        ):
            created.append(name)
        elif ep <= 8:
            missing.append(name)

    files = [p for p in COPY.iterdir() if p.is_file()]
    non_md = [p.name for p in files if p.suffix.lower() != ".md"]
    if non_md:
        raise SystemExit(f"copy/ contains non-Markdown files: {non_md}")
    for path in files:
        text = path.read_text(encoding="utf-8")
        if "github.com/Shahbazi-Amir/vid_pipeline" in text:
            raise SystemExit(f"internal GitHub source leaked into {path}")
        for required in ("**توضیحات:**", "**مدت‌زمان کل:**", "**لینک منبع اصلی:**"):
            if required not in text:
                raise SystemExit(f"missing {required} in {path}")

    summary = {"created_count": len(created), "created": created, "missing_requested": missing}
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return summary


if __name__ == "__main__":
    build()
