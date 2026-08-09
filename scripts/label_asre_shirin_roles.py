from __future__ import annotations

import json
import re
import sys
from collections import defaultdict
from pathlib import Path

TIMESTAMP_BLOCK = re.compile(
    r"\[(\d{2}):(\d{2}):(\d{2})\s*→\s*(\d{2}):(\d{2}):(\d{2})\]\s+\*\*([^*]+)\*\*"
)
GENERIC_SPEAKER = re.compile(r"^گوینده\s+([۰-۹0-9]+)$")


def seconds(h: str, m: str, s: str) -> int:
    return int(h) * 3600 + int(m) * 60 + int(s)


def parse_timeline(path: Path) -> list[dict[str, object]]:
    text = path.read_text(encoding="utf-8")
    rows: list[dict[str, object]] = []
    for match in TIMESTAMP_BLOCK.finditer(text):
        start = seconds(match.group(1), match.group(2), match.group(3))
        end = seconds(match.group(4), match.group(5), match.group(6))
        label = match.group(7).strip()
        if end >= start:
            rows.append({"start": start, "end": end, "duration": end - start, "label": label})
    if not rows:
        raise SystemExit(f"No timestamped speaker blocks found: {path}")
    return rows


def replace_labels(text: str, mapping: dict[str, str]) -> str:
    # Replace longest labels first and only in explicit speaker-label contexts.
    for old in sorted(mapping, key=len, reverse=True):
        new = mapping[old]
        text = text.replace(f"**{old}**", f"**{new}**")
        text = re.sub(rf"(?m)^{re.escape(old)}:$", f"{new}:", text)
    return text


def main() -> None:
    if len(sys.argv) != 3:
        raise SystemExit("usage: label_asre_shirin_roles.py COLLECTION_ROOT EPISODE")
    root = Path(sys.argv[1])
    episode = int(sys.argv[2])
    timestamped = root / "timestamped" / f"{episode}.md"
    markdown = root / "md" / f"{episode}.md"
    text_path = root / "txt" / f"{episode}.txt"
    for path in (timestamped, markdown, text_path):
        if not path.is_file() or path.stat().st_size == 0:
            raise SystemExit(f"Required transcript is missing: {path}")

    rows = parse_timeline(timestamped)
    totals: dict[str, float] = defaultdict(float)
    first_start: dict[str, float] = {}
    first_duration: dict[str, float] = {}
    opening_totals: dict[str, float] = defaultdict(float)
    for row in rows:
        label = str(row["label"])
        duration = float(row["duration"])
        start = float(row["start"])
        end = float(row["end"])
        totals[label] += duration
        first_start.setdefault(label, start)
        first_duration.setdefault(label, duration)
        overlap = max(0.0, min(end, 120.0) - max(start, 0.0))
        opening_totals[label] += overlap

    labels = sorted(totals, key=lambda value: (first_start[value], -totals[value], value))
    if len(labels) < 2:
        raise SystemExit(f"Expected at least two diarized speakers; got {labels}")

    # User-supplied program structure: Ms. Motavalian opens the program. Select
    # the earliest substantial speaker; if the first turn is tiny, prefer the
    # strongest speaker in the first 120 seconds among speakers starting early.
    substantial = [label for label in labels if first_duration[label] >= 4.0]
    if substantial:
        host = min(substantial, key=lambda value: (first_start[value], -opening_totals[value]))
    else:
        host = max(labels, key=lambda value: (opening_totals[value], -first_start[value]))

    remaining = [label for label in labels if label != host]
    doctor = max(remaining, key=lambda value: (totals[value], -first_start[value]))
    participants = [
        label
        for label in sorted(remaining, key=lambda value: (first_start[value], -totals[value], value))
        if label != doctor
    ]

    mapping = {host: "خانم متولیان", doctor: "دکتر کمیل رودی"}
    for index, label in enumerate(participants, 1):
        mapping[label] = f"شرکت‌کننده {index}"

    doctor_others = sorted((totals[label] for label in participants), reverse=True)
    next_nonhost = doctor_others[0] if doctor_others else 0.0
    doctor_ratio = totals[doctor] / max(next_nonhost, 1.0)
    host_is_first = first_start[host] == min(first_start.values())

    diagnostics = {
        "episode": episode,
        "method": "opening-host-and-dominant-nonhost-v1",
        "user_program_structure": {
            "host": "خانم متولیان",
            "expert": "دکتر کمیل رودی",
            "other_speakers": "participants",
            "host_speaks_at_beginning": True,
        },
        "raw_speakers": labels,
        "raw_speaker_count": len(labels),
        "duration_seconds": {label: round(totals[label], 3) for label in labels},
        "first_start_seconds": {label: round(first_start[label], 3) for label in labels},
        "opening_120s_seconds": {label: round(opening_totals[label], 3) for label in labels},
        "mapping": mapping,
        "host_selection": {
            "raw_label": host,
            "is_earliest_speaker": host_is_first,
            "first_turn_seconds": round(first_duration[host], 3),
        },
        "doctor_selection": {
            "raw_label": doctor,
            "dominant_nonhost_duration_ratio_vs_next": round(doctor_ratio, 3),
        },
        "status": "mapped",
        "warning": (
            "Doctor/participant assignment is heuristic and should be spot-checked when the dominant-nonhost ratio is low."
            if doctor_ratio < 1.20 and participants
            else ""
        ),
    }

    for path in (timestamped, markdown, text_path):
        original = path.read_text(encoding="utf-8")
        updated = replace_labels(original, mapping)
        if updated == original:
            raise SystemExit(f"No speaker labels were replaced in {path}")
        path.write_text(updated, encoding="utf-8")

    roles_dir = root / "roles"
    roles_dir.mkdir(parents=True, exist_ok=True)
    (roles_dir / f"{episode}.json").write_text(
        json.dumps(diagnostics, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps({"episode": episode, "mapping": mapping, "warning": diagnostics["warning"]}, ensure_ascii=False))


if __name__ == "__main__":
    main()
