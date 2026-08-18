"""Record source provenance and expose it in user-facing transcript files."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

_DIRECT_KEYS = (
    "original_download_url",
    "original_media_url",
    "direct_media_url",
    "download_url",
)
_PAGE_KEYS = ("source_page_url", "original_page_url", "url")
_ARCHIVE_KEYS = ("archive_url", "archived_media_url")


def _url(value: Any) -> str:
    text = str(value or "").strip()
    return text if text.startswith(("http://", "https://")) else ""


def _first(metadata: dict[str, Any], keys: tuple[str, ...]) -> str:
    provenance = metadata.get("provenance") or {}
    for key in keys:
        value = _url(provenance.get(key)) or _url(metadata.get(key))
        if value:
            return value
    return ""


def resolve_provenance(metadata: dict[str, Any]) -> dict[str, str]:
    """Resolve canonical source links while keeping archive URLs separate."""

    direct = _first(metadata, _DIRECT_KEYS)
    page = _first(metadata, _PAGE_KEYS)
    archive = _first(metadata, _ARCHIVE_KEYS)
    legacy = _url(metadata.get("source_url"))

    if legacy:
        if "/releases/download/" in legacy and not archive:
            archive = legacy
        elif not direct:
            direct = legacy

    if direct and page == direct:
        page = ""
    if archive and direct == archive:
        direct = ""

    return {
        "original_download_url": direct,
        "source_page_url": page,
        "archive_url": archive,
    }


def record_provenance(
    job_root: str | Path,
    *,
    original_download_url: str = "",
    source_page_url: str = "",
    archive_url: str = "",
) -> dict[str, str]:
    root = Path(job_root)
    source_path = root / "source.json"
    metadata: dict[str, Any] = {}
    if source_path.is_file():
        metadata = json.loads(source_path.read_text(encoding="utf-8"))
    metadata.setdefault("schema_version", 3)
    current = dict(metadata.get("provenance") or {})
    if _url(original_download_url):
        current["original_download_url"] = _url(original_download_url)
    if _url(source_page_url):
        current["source_page_url"] = _url(source_page_url)
    if _url(archive_url):
        current["archive_url"] = _url(archive_url)
    metadata["provenance"] = current
    resolved = resolve_provenance(metadata)
    metadata.update({key: value for key, value in resolved.items() if value})
    source_path.parent.mkdir(parents=True, exist_ok=True)
    source_path.write_text(json.dumps(metadata, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return resolved


def _markdown_header(provenance: dict[str, str]) -> str:
    lines = ["## منبع فایل"]
    if provenance.get("original_download_url"):
        lines.append(f"- دانلود مستقیم فایل اصلی: {provenance['original_download_url']}")
    if provenance.get("source_page_url"):
        lines.append(f"- صفحه منبع: {provenance['source_page_url']}")
    if provenance.get("archive_url"):
        lines.append(f"- نسخه آرشیوی: {provenance['archive_url']}")
    return "\n".join(lines) + "\n\n"


def _text_header(provenance: dict[str, str]) -> str:
    lines = ["منبع فایل:"]
    if provenance.get("original_download_url"):
        lines.append(f"دانلود مستقیم فایل اصلی: {provenance['original_download_url']}")
    if provenance.get("source_page_url"):
        lines.append(f"صفحه منبع: {provenance['source_page_url']}")
    if provenance.get("archive_url"):
        lines.append(f"نسخه آرشیوی: {provenance['archive_url']}")
    return "\n".join(lines) + "\n\n"


def annotate_delivery(job_root: str | Path) -> dict[str, str]:
    root = Path(job_root)
    source_path = root / "source.json"
    metadata = json.loads(source_path.read_text(encoding="utf-8")) if source_path.is_file() else {}
    provenance = resolve_provenance(metadata)
    if not any(provenance.values()):
        return provenance

    delivery = root / "delivery"
    for name in ("transcript.md", "transcript.timestamped.md"):
        path = delivery / name
        if not path.is_file():
            continue
        text = path.read_text(encoding="utf-8")
        if "دانلود مستقیم فایل اصلی:" in text or "## منبع فایل" in text:
            continue
        path.write_text(_markdown_header(provenance) + text, encoding="utf-8")

    text_path = delivery / "transcript.txt"
    if text_path.is_file():
        text = text_path.read_text(encoding="utf-8")
        if "دانلود مستقیم فایل اصلی:" not in text and not text.startswith("منبع فایل:\n"):
            text_path.write_text(_text_header(provenance) + text, encoding="utf-8")
    return provenance


def record_and_annotate(
    job_root: str | Path,
    *,
    original_download_url: str = "",
    source_page_url: str = "",
    archive_url: str = "",
) -> dict[str, str]:
    record_provenance(
        job_root,
        original_download_url=original_download_url,
        source_page_url=source_page_url,
        archive_url=archive_url,
    )
    return annotate_delivery(job_root)


def main() -> int:
    parser = argparse.ArgumentParser(description="Record and apply transcript source provenance.")
    parser.add_argument("job_root", type=Path)
    parser.add_argument("--original-download-url", default="")
    parser.add_argument("--source-page-url", default="")
    parser.add_argument("--archive-url", default="")
    args = parser.parse_args()
    result = record_and_annotate(
        args.job_root,
        original_download_url=args.original_download_url,
        source_page_url=args.source_page_url,
        archive_url=args.archive_url,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
