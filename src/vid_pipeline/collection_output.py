"""Materialize validated GitHub transcript artifacts into a numbered collection."""

from __future__ import annotations

import re
import shutil
import uuid
from pathlib import Path

_FINAL_FILES = {
    "transcript.md": ("md", ".md"),
    "transcript.timestamped.md": ("timestamped", ".md"),
    "transcript.txt": ("txt", ".txt"),
}


def infer_result_number(source: Path, explicit: int | None = None) -> int:
    if explicit is not None:
        if explicit < 1:
            raise ValueError("result number must be positive")
        return explicit
    match = re.match(r"^(\d+)(?:[. _-]|$)", source.name)
    if not match:
        raise ValueError(
            "Could not infer result number from filename; use --result-number."
        )
    return int(match.group(1))


def materialize_collection_output(
    downloaded: Path,
    collection_root: Path,
    source: Path,
    *,
    result_number: int | None = None,
) -> Path:
    downloaded = downloaded.resolve()
    if not downloaded.is_dir():
        raise ValueError(f"downloaded result directory does not exist: {downloaded}")

    number = infer_result_number(source, result_number)
    files = {item.name: item for item in downloaded.iterdir() if item.is_file()}
    if set(files) != set(_FINAL_FILES):
        raise ValueError(
            "validated result must contain exactly the three final transcript files"
        )

    root = collection_root.resolve()
    targets: dict[Path, Path] = {}
    for filename, (folder, suffix) in _FINAL_FILES.items():
        target = root / folder / f"{number}{suffix}"
        source_file = files[filename]
        if target.exists() and target.read_bytes() != source_file.read_bytes():
            raise ValueError(
                f"collection output already exists with different content: {target}"
            )
        targets[source_file] = target

    for source_file, target in targets.items():
        target.parent.mkdir(parents=True, exist_ok=True)
        if target.exists():
            continue
        temporary = target.with_name(f".{target.name}.{uuid.uuid4().hex}.tmp")
        shutil.copy2(source_file, temporary)
        temporary.replace(target)

    shutil.rmtree(downloaded)
    parent = downloaded.parent
    if parent.name == "github-results" and parent.exists() and not any(parent.iterdir()):
        parent.rmdir()
    return root
