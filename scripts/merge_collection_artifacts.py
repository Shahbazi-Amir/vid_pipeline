from __future__ import annotations

import shutil
import sys
from pathlib import Path

ALLOWED = {
    "md": ".md",
    "timestamped": ".md",
    "txt": ".txt",
    "roles": ".json",
    "sources": ".json",
    "review/md": ".md",
    "review/timestamped": ".md",
    "review/txt": ".txt",
}


def main() -> None:
    if len(sys.argv) not in {3, 4} or (
        len(sys.argv) == 4 and sys.argv[3] != "--skip-existing-complete-base"
    ):
        raise SystemExit(
            "usage: merge_collection_artifacts.py STAGING TARGET "
            "[--skip-existing-complete-base]"
        )
    staging = Path(sys.argv[1]).resolve()
    target = Path(sys.argv[2]).resolve()
    skip_existing_complete_base = len(sys.argv) == 4
    if not staging.is_dir():
        raise SystemExit("staging directory does not exist")

    files = [path for path in staging.rglob("*") if path.is_file()]
    if not files:
        raise SystemExit("no collection artifact files were downloaded")

    validated: list[tuple[Path, Path, str]] = []
    for source in files:
        relative = source.relative_to(staging)
        parent = relative.parent.as_posix()
        expected_suffix = ALLOWED.get(parent)
        if expected_suffix is None or source.suffix != expected_suffix or not source.stem.isdigit():
            raise SystemExit(f"unexpected collection artifact path: {relative}")
        validated.append((source, relative, parent))

    complete_numbers: set[str] = set()
    if skip_existing_complete_base:
        numbers = {source.stem for source, _, parent in validated if parent in {"md", "timestamped", "txt"}}
        for number in numbers:
            if all(
                (target / kind / f"{number}.{suffix}").is_file()
                and (target / kind / f"{number}.{suffix}").stat().st_size > 0
                for kind, suffix in (("md", "md"), ("timestamped", "md"), ("txt", "txt"))
            ):
                complete_numbers.add(number)

    merged = 0
    skipped = 0
    for source, relative, parent in validated:
        if parent in {"md", "timestamped", "txt", "roles", "sources"} and source.stem in complete_numbers:
            skipped += 1
            continue
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

    print(f"Skipped {skipped} files for existing complete base results")
    print(f"Merged {merged} new collection files")


if __name__ == "__main__":
    main()
