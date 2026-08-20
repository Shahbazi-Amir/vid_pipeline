#!/usr/bin/env python3
"""Build the readable Markdown-only copy/ directory from repository outputs."""
from __future__ import annotations

import json
import re
import shutil
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
OUTPUTS = ROOT / "outputs"
COPY = ROOT / "copy"

CHEHELSTOUN_SOURCE_PAGE = "https://radio.iranseda.ir/Program/?VALID=TRUE&ch=57&m=090513"
KETAB_BAZ_SOURCE_PAGE = "https://taaghche.com/audiobook/255204"
FINUP_SOURCE_PAGE = "https://youtu.be/bpelPbGcBMc"
MIZAN_SOURCE_PAGE = ""
SHERAKAT_SOURCE_PAGE = ""
BANK_MELLAT_SOURCE_PAGE = ""
AI_MARKERS = ("chatgpt", "openai", "gpt", "llm", "claude", "gemini", "copilot")


def load_json(path: Path) -> dict[str, Any]:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError, UnicodeDecodeError):
        return {}


def clean_text(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "").strip())


def human_verification_complete(root: Path) -> bool:
    """Only evidence-backed human audio verification can make copy/ final."""
    candidates = [
        root / "human" / "verification.json",
        root / "final" / "human-verification.json",
    ]
    data = next((load_json(path) for path in candidates if path.is_file()), {})
    reviewer = clean_text(data.get("reviewer")).casefold()
    if any(marker in reviewer for marker in AI_MARKERS):
        return False
    return bool(
        data.get("status") == "human_verified"
        and data.get("review_status") == "human_verified"
        and data.get("verification_method") == "human_audio"
        and data.get("human_audio_verification") is True
        and clean_text(data.get("source_audio_sha256"))
        and clean_text(data.get("reviewer"))
        and not data.get("unresolved_items")
    )


def finalized_path_for(root: Path) -> Path | None:
    if not human_verification_complete(root):
        return None
    try:
        rel = root.relative_to(OUTPUTS)
    except ValueError:
        return None
    if not rel.parts or rel.parts[0] in {"finalized", "review-ready"}:
        return None
    candidate = OUTPUTS / "finalized" / rel / "transcript.md"
    return candidate if candidate.is_file() and candidate.stat().st_size > 0 else None


def transcript_for(root: Path) -> tuple[Path | None, str]:
    canonical_final = finalized_path_for(root)
    if canonical_final is not None:
        return canonical_final, "نهایی؛ بازبینی انسانی مبتنی بر صوت"

    for path in (root / "delivery" / "transcript.md", root / "final" / "transcript.final.md"):
        if path.is_file() and path.stat().st_size > 0:
            return path, "ماشینی/AI؛ نیازمند راستی‌آزمایی انسانی صوت"
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


def clean_body(text: str) -> str:
    kept: list[str] = []
    for line in text.lstrip("\ufeff\n\r").splitlines():
        lowered = line.lower()
        if "github.com/shahbazi-amir/vid_pipeline" in lowered:
            continue
        if line.strip().startswith("- نسخه آرشیوی:") or line.strip().startswith("**منبع:**"):
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
    ]
    if source_page:
        header.append(f"- **منبع اصلی:** {source_page}")
    header += ["", "---", ""]
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
        ok = write_copy(filename=name, program="چهلستون", episode=str(ep), root=root,
                        title=title, description=f"قسمت {ep} از مجموعه رادیویی چهلستون درباره سواد مالی و اقتصاد خانواده.",
                        source_page=CHEHELSTOUN_SOURCE_PAGE)
        (created if ok else missing).append(name)

    cases = [
        ("کتاب باز.md", "کتاب باز", "فصل ۵ - قسمت ۶۸", OUTPUTS/"ketab-baz"/"01",
         "کتاب باز - دکتر کمیل رودی", "گفت‌وگوی سروش صحت با دکتر کمیل رودی درباره سواد مالی در برنامه کتاب باز.", KETAB_BAZ_SOURCE_PAGE),
        ("میزان.md", "میزان", "1", OUTPUTS/"mizan"/"01",
         "میزان", "متن برنامه میزانِ پردازش‌شده در پروژه.", MIZAN_SOURCE_PAGE),
        ("شراکت.md", "شراکت", "1", OUTPUTS/"voice-260817-165035"/"01",
         "شراکت", "متن فایل صوتی شراکتِ اضافه‌شده به مجموعه داده پروژه.", SHERAKAT_SOURCE_PAGE),
    ]
    for name,program,episode,root,title,description,source_page in cases:
        ok=write_copy(filename=name,program=program,episode=episode,root=root,title=title,description=description,source_page=source_page)
        (created if ok else missing).append(name)

    finup_root=first_completed_child(OUTPUTS/"finup")
    name="فناپ.md"
    ok=bool(finup_root) and write_copy(filename=name,program="فیناپ",episode="رویداد ۲۱",root=finup_root,
        title="سواد مالی چه هست و چه نیست؟ - کمیل رودی",
        description="ارائه دکتر کمیل رودی در بیست‌ویکمین رویداد فیناپ درباره تعریف و مرزهای سواد مالی.",
        source_page=FINUP_SOURCE_PAGE)
    (created if ok else missing).append(name)

    for ep in range(1,12):
        root=OUTPUTS/"bankmellatt"/str(ep); name=f"بانک ملت {ep}.md"
        ok=write_copy(filename=name,program="بانک ملت",episode=str(ep),root=root,title=f"بانک ملت - قسمت {ep}",
                      description=f"قسمت {ep} از مجموعه آموزشی بانک ملت؛ متن پردازش‌شده فایل موجود.",source_page=BANK_MELLAT_SOURCE_PAGE)
        if ok: created.append(name)
        elif ep<=8: missing.append(name)

    files=[p for p in COPY.iterdir() if p.is_file()]
    non_md=[p.name for p in files if p.suffix.lower()!=".md"]
    if non_md: raise SystemExit(f"copy/ contains non-Markdown files: {non_md}")
    for path in files:
        text=path.read_text(encoding="utf-8")
        if "github.com/Shahbazi-Amir/vid_pipeline" in text:
            raise SystemExit(f"internal GitHub source leaked into {path}")
        for required in ("**توضیحات:**","**مدت‌زمان کل:**"):
            if required not in text: raise SystemExit(f"missing {required} in {path}")
        if "**منبع اصلی:**" in text:
            source_line=next(line for line in text.splitlines() if "**منبع اصلی:**" in line)
            if "http" not in source_line: raise SystemExit(f"non-URL source in {path}")

    summary={"created_count":len(created),"created":created,"missing_requested":missing}
    print(json.dumps(summary,ensure_ascii=False,indent=2))
    return summary


if __name__ == "__main__":
    build()
