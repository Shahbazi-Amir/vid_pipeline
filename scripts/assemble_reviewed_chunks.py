#!/usr/bin/env python3
"""Assemble independently reviewed transcript chunks without repeated headers."""

from __future__ import annotations

import argparse
import re
from pathlib import Path


def extract_body(markdown: str) -> str:
    """Return the reviewed body produced by ``vid-pipeline edit``."""

    lines = markdown.splitlines()
    note_index = next(
        (index for index, line in enumerate(lines) if line.startswith("> این متن فقط")),
        None,
    )
    if note_index is None:
        raise ValueError("reviewed chunk is missing the preservation notice")
    return "\n".join(lines[note_index + 1 :]).strip()


def markdown_to_text(markdown: str) -> str:
    lines = []
    for raw_line in markdown.splitlines():
        line = re.sub(r"^(#{1,6}\s+|>\s*|[-*+]\s+)", "", raw_line)
        lines.append(line.replace("**", "").replace("`", "").rstrip())
    return "\n".join(lines).strip() + "\n"


def assemble(directory: Path, title: str, source_url: str) -> str:
    paths = sorted(directory.glob("chunk-*.md"))
    if not paths:
        raise ValueError("no reviewed chunk markdown files found")
    bodies = [extract_body(path.read_text(encoding="utf-8")) for path in paths]
    heading = title.strip() or "متن نهایی بازبینی‌شده"
    lines = [f"# {heading}", ""]
    if source_url.strip():
        lines.extend([f"منبع: {source_url.strip()}  ", ""])
    lines.extend(
        [
            "> این متن به‌صورت بخش‌بندی‌شده با مدل محلی بازبینی شده است؛ "
            "معنا، ترتیب و اطلاعات گفتار حفظ شده‌اند.",
            "",
            "\n\n".join(body for body in bodies if body),
            "",
        ]
    )
    return "\n".join(lines).rstrip() + "\n"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("directory", type=Path)
    parser.add_argument("--markdown", required=True, type=Path)
    parser.add_argument("--text", required=True, type=Path)
    parser.add_argument("--title", default="")
    parser.add_argument("--source-url", default="")
    args = parser.parse_args()

    markdown = assemble(args.directory, args.title, args.source_url)
    args.markdown.parent.mkdir(parents=True, exist_ok=True)
    args.text.parent.mkdir(parents=True, exist_ok=True)
    args.markdown.write_text(markdown, encoding="utf-8")
    args.text.write_text(markdown_to_text(markdown), encoding="utf-8")


if __name__ == "__main__":
    main()
