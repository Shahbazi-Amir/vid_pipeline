from __future__ import annotations

import shutil
import sys
from pathlib import Path

ALLOWED = {
    "md": ".md",
    "timestamped": ".md",
    "txt": ".txt",
    "review/md": ".md",
    "review/timestamped": ".md",
    "review/txt": ".txt",
}


def main() -> None:
    if len(sys.argv) != 3:
        raise SystemExit("usage: merge_collection_artifacts.py STAGING TARGET")
    staging = Path(sys.argv[1]).resolve()
    target = Path(sys.argv[2]).resolve()
    if not staging.is_dir():
        raise SystemExit("staging directory does not exist")

    files = [path for path in staging.rglob("*") if path.is_file()]
    if not files:
        raise SystemExit("no collection artifact files were downloaded")

    merged = 0
    for source in files:
        relative = source.relative_to(staging)
        parent = relative.parent.as_posix()
        expected_suffix = ALLOWED.get(parent)
        if expected_suffix is None or source.suffix != expected_suffix or not source.stem.isdigit():
            raise SystemExit(f"unexpected collection artifact path: {relative}")
        destination = target / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        if destination.exists():
            if destination.read_bytes() != source.read_bytes():
                raise SystemExit(f"refusing to overwrite different existing output: {destination}")
            continue
        temporary = destination.with_name(f".{destination.name}.tmp")
        shutil.copy2(source, temporary)
        temporary.replace(destination)
        merged += 1

    print(f"Merged {merged} new collection files")


if __name__ == "__main__":
    main()
