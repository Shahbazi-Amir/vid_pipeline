from __future__ import annotations

import json
import re
import sys
from collections import defaultdict
from pathlib import Path

from label_asre_shirin_roles import parse_timeline, replace_labels

HOST_MAX_FIRST_START_SECONDS = 15.0
HOST_MIN_FIRST_TURN_SECONDS = 3.0
DOCTOR_ADDRESS_WINDOW_SECONDS = 35.0


def main() -> None:
    if len(sys.argv) != 3:
        raise SystemExit("usage: label_khane_to_roles.py COLLECTION_ROOT EPISODE")
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
    for row in rows:
        label = str(row["label"])
        totals[label] += float(row["duration"])
        first_start.setdefault(label, float(row["start"]))
        first_duration.setdefault(label, float(row["duration"]))

    labels = sorted(totals, key=lambda value: (first_start[value], -totals[value], value))
    if len(labels) < 2:
        raise SystemExit(f"Expected at least two diarized speakers; got {labels}")

    substantial = [
        label for label in labels
        if first_start[label] <= HOST_MAX_FIRST_START_SECONDS
        and first_duration[label] >= HOST_MIN_FIRST_TURN_SECONDS
    ]
    host = min(substantial, key=lambda value: (first_start[value], -totals[value])) if substantial else None

    doctor = None
    doctor_evidence = "insufficient"
    if host is not None and len(labels) == 2:
        doctor = next(label for label in labels if label != host)
        doctor_evidence = "user_supplied_two_person_program_structure"
    elif host is not None:
        address = re.compile(r"دکتر(?:\s+کمیل)?\s+رودی")
        candidates: list[str] = []
        for index, row in enumerate(rows):
            if str(row["label"]) != host or not address.search(str(row.get("text") or "")):
                continue
            address_end = float(row["end"])
            for candidate in rows[index + 1:]:
                if float(candidate["start"]) > address_end + DOCTOR_ADDRESS_WINDOW_SECONDS:
                    break
                label = str(candidate["label"])
                if label != host:
                    candidates.append(label)
                    break
        unique = sorted(set(candidates))
        if len(unique) == 1:
            doctor = unique[0]
            doctor_evidence = "explicit_host_address_followed_by_response"

    mapping: dict[str, str] = {}
    unresolved: list[str] = []
    if host is not None:
        mapping[host] = "فرهاد جم"
    if doctor is not None:
        mapping[doctor] = "دکتر کمیل رودی"

    participant_index = 1
    unresolved_index = 1
    for label in labels:
        if label in mapping:
            continue
        if host is None or doctor is None:
            mapping[label] = f"گوینده نامشخص {unresolved_index}"
            unresolved.append(label)
            unresolved_index += 1
        else:
            mapping[label] = f"شرکت‌کننده {participant_index}"
            participant_index += 1

    status = "mapped" if host is not None and doctor is not None and not unresolved else "partially_unresolved"
    diagnostics = {
        "episode": episode,
        "method": "khane-to-user-supplied-host-guest-conservative-v1",
        "user_program_structure": {
            "program": "خانه تو",
            "host": "فرهاد جم",
            "guest": "دکتر کمیل رودی"
        },
        "raw_speakers": labels,
        "raw_speaker_count": len(labels),
        "mapping": mapping,
        "host_selection": {"raw_label": host, "resolved": host is not None},
        "doctor_selection": {"raw_label": doctor, "resolved": doctor is not None, "evidence": doctor_evidence},
        "unresolved_raw_labels": unresolved,
        "status": status,
    }

    for path in (timestamped, markdown, text_path):
        original = path.read_text(encoding="utf-8")
        updated = replace_labels(original, mapping)
        if updated == original:
            raise SystemExit(f"No speaker labels were replaced in {path}")
        path.write_text(updated, encoding="utf-8")

    roles = root / "roles"
    roles.mkdir(parents=True, exist_ok=True)
    (roles / f"{episode}.json").write_text(
        json.dumps(diagnostics, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps({"episode": episode, "mapping": mapping, "status": status}, ensure_ascii=False))


if __name__ == "__main__":
    main()
