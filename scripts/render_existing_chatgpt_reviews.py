from __future__ import annotations

from pathlib import Path

from vid_pipeline.llm_review import (
    _atomic_write,
    render_review_markdown,
    render_review_text,
    validate_review,
)


def main() -> int:
    changed = 0
    for reviewed_timed in sorted(Path("outputs").glob("*/review/timestamped/*.md")):
        if not reviewed_timed.is_file() or not reviewed_timed.stat().st_size:
            continue
        number = reviewed_timed.stem
        if not number.isdigit():
            continue
        collection = reviewed_timed.parents[2]
        source = collection / "timestamped" / f"{number}.md"
        if not source.is_file() or not source.stat().st_size:
            raise SystemExit(f"missing base timestamped source: {source}")

        reviewed_md = collection / "review" / "md" / f"{number}.md"
        reviewed_txt = collection / "review" / "txt" / f"{number}.txt"
        if (
            reviewed_md.is_file()
            and reviewed_md.stat().st_size
            and reviewed_txt.is_file()
            and reviewed_txt.stat().st_size
        ):
            continue

        source_text = source.read_text(encoding="utf-8")
        reviewed_text = reviewed_timed.read_text(encoding="utf-8")
        blocks = validate_review(source_text, reviewed_text)
        _atomic_write(reviewed_md, render_review_markdown(blocks))
        _atomic_write(reviewed_txt, render_review_text(blocks))
        changed += 1
        print(f"rendered {collection} review {number} locally")

    print(f"rendered_count={changed}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
