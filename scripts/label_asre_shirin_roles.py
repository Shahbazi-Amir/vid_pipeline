from __future__ import annotations

import json
import re
import sys
from collections import defaultdict
from pathlib import Path

TIMESTAMP_BLOCK = re.compile(
    r"\[(\d{2}):(\d{2}):(\d{2})\s*→\s*(\d{2}):(\d{2}):(\d{2})\]\s+\*\*([^*]+)\*\*"
)

HOST_MAX_FIRST_START_SECONDS = 12.0
HOST_MIN_FIRST_TURN_SECONDS = 4.0
DOCTOR_MIN_DOMINANCE_RATIO = 1.20


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

    # The user supplied only one structural identity cue: Ms. Motavalian opens
    # the program. Apply that identity only when the diarization actually shows
    # a substantial speaker beginning near time zero. Otherwise preserve an
    # explicit unresolved label instead of inventing a name.
    substantial = [
        label
        for label in labels
        if first_duration[label] >= HOST_MIN_FIRST_TURN_SECONDS
        and first_start[label] <= HOST_MAX_FIRST_START_SECONDS
    ]
    host = (
        min(substantial, key=lambda value: (first_start[value], -opening_totals[value]))
        if substantial
        else None
    )

    remaining = [label for label in labels if label != host]
    doctor_candidate = max(remaining, key=lambda value: (totals[value], -first_start[value]))
    other_nonhost = [label for label in remaining if label != doctor_candidate]
    next_nonhost_duration = max((totals[label] for label in other_nonhost), default=0.0)
    doctor_ratio = totals[doctor_candidate] / max(next_nonhost_duration, 1.0)
    doctor_resolved = len(remaining) == 1 or doctor_ratio >= DOCTOR_MIN_DOMINANCE_RATIO
    doctor = doctor_candidate if doctor_resolved else None

    mapping: dict[str, str] = {}
    unresolved: list[str] = []
    if host is not None:
        mapping[host] = "خانم متولیان"
    if doctor is not None:
        mapping[doctor] = "دکتر کمیل رودی"

    participant_index = 1
    for label in sorted(labels, key=lambda value: (first_start[value], -totals[value], value)):
        if label in mapping:
            continue
        if label == doctor_candidate and not doctor_resolved:
            mapping[label] = "گوینده نامشخص (کاندید دکتر کمیل رودی)"
            unresolved.append(label)
            continue
        if host is None and label == labels[0]:
            mapping[label] = "گوینده نامشخص (کاندید خانم متولیان)"
            unresolved.append(label)
            continue
        mapping[label] = f"شرکت‌کننده {participant_index}"
        participant_index += 1

    host_is_first = host is not None and first_start[host] == min(first_start.values())
    status = "mapped" if host is not None and doctor is not None else "partially_unresolved"
    warnings: list[str] = []
    if host is None:
        warnings.append("Host identity unresolved: no substantial diarized speaker starts near the beginning.")
    if doctor is None:
        warnings.append(
            "Doctor identity unresolved: dominant non-host evidence is insufficient; identity was not invented."
        )

    diagnostics = {
        "episode": episode,
        "method": "conservative-opening-host-and-dominant-nonhost-v2",
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
            "resolved": host is not None,
            "is_earliest_speaker": host_is_first,
            "first_turn_seconds": round(first_duration[host], 3) if host is not None else None,
            "max_first_start_seconds": HOST_MAX_FIRST_START_SECONDS,
            "min_first_turn_seconds": HOST_MIN_FIRST_TURN_SECONDS,
        },
        "doctor_selection": {
            "raw_label": doctor,
            "candidate_raw_label": doctor_candidate,
            "resolved": doctor is not None,
            "dominant_nonhost_duration_ratio_vs_next": round(doctor_ratio, 3),
            "required_ratio": DOCTOR_MIN_DOMINANCE_RATIO,
        },
        "unresolved_raw_labels": unresolved,
        "status": status,
        "warnings": warnings,
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
    print(
        json.dumps(
            {"episode": episode, "mapping": mapping, "status": status, "warnings": warnings},
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()
