from __future__ import annotations

import argparse
from pathlib import Path

BASE_GROUPS = (
    ("md", ".md"),
    ("timestamped", ".md"),
    ("txt", ".txt"),
)
REVIEW_GROUPS = (
    ("review/md", ".md"),
    ("review/timestamped", ".md"),
    ("review/txt", ".txt"),
)


def parse_numbers(spec: str) -> set[int]:
    values: set[int] = set()
    for part in spec.split(","):
        part = part.strip()
        if not part:
            continue
        if "-" in part:
            start, end = (int(item) for item in part.split("-", 1))
            if start < 1 or end < start:
                raise ValueError("invalid number range")
            values.update(range(start, end + 1))
        else:
            value = int(part)
            if value < 1:
                raise ValueError("result numbers must be positive")
            values.add(value)
    return values


def numbers_for(root: Path, folder: str, suffix: str) -> set[int]:
    path = root / folder
    if not path.is_dir():
        return set()
    result: set[int] = set()
    for item in path.iterdir():
        if (
            item.is_file()
            and item.suffix == suffix
            and item.stem.isdigit()
            and item.stat().st_size > 0
        ):
            result.add(int(item.stem))
    return result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("root", type=Path)
    parser.add_argument("--numbers", default="")
    parser.add_argument(
        "--base-only",
        action="store_true",
        help="Verify only raw transcript outputs and do not require AI-review outputs.",
    )
    args = parser.parse_args()

    groups = BASE_GROUPS if args.base_only else BASE_GROUPS + REVIEW_GROUPS
    root = args.root.resolve()
    observed = [numbers_for(root, folder, suffix) for folder, suffix in groups]
    expected = parse_numbers(args.numbers) if args.numbers else observed[0]
    if not expected:
        raise SystemExit("collection contains no complete numbered outputs")
    for (folder, _), actual in zip(groups, observed, strict=True):
        missing = sorted(expected - actual)
        extra = sorted(actual - expected) if args.numbers else []
        if missing or extra:
            raise SystemExit(
                f"collection verification failed for {folder}: missing={missing}, extra={extra}"
            )
    mode = "base transcript" if args.base_only else "reviewed transcript"
    print(f"Verified {len(expected)} complete {mode} results")


if __name__ == "__main__":
    main()
