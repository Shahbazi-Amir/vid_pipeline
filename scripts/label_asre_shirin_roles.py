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
DOCTOR_ADDRESS_WINDOW_SECONDS = 30.0
EARLY_IDENTITY_WINDOW_SECONDS = 180.0


def seconds(h: str, m: str, s: str) -> int:
    return int(h) * 3600 + int(m) * 60 + int(s)


def parse_timeline(path: Path) -> list[dict[str, object]]:
    text = path.read_text(encoding="utf-8")
    rows: list[dict[str, object]] = []
    matches = list(TIMESTAMP_BLOCK.finditer(text))
    for index, match in enumerate(matches):
        start = seconds(match.group(1), match.group(2), match.group(3))
        end = seconds(match.group(4), match.group(5), match.group(6))
        label = match.group(7).strip()
        body_end = matches[index + 1].start() if index + 1 < len(matches) else len(text)
        body = text[match.end():body_end].strip()
        if end >= start:
            rows.append({
                "start": start,
                "end": end,
                "duration": end - start,
                "label": label,
                "text": body,
            })
    if not rows:
        raise SystemExit(f"No timestamped speaker blocks found: {path}")
    return rows


def replace_labels(text: str, mapping: dict[str, str]) -> str:
    for old in sorted(mapping, key=len, reverse=True):
        new = mapping[old]
        text = text.replace(f"**{old}**", f"**{new}**")
        text = re.sub(rf"(?m)^{re.escape(old)}:$", f"{new}:", text)
    return text


def _identity_normalized(text: str) -> str:
    """Normalize only narrow, observed ASR confusions used for identity evidence."""

    value = text.replace("ي", "ی").replace("ك", "ک")
    # Observed in episode 1: «آقای دفتر رودی» for «آقای دکتر رودی».
    value = re.sub(r"\bدفتر\s+رودی\b", "دکتر رودی", value)
    # Observed spacing/colloquial variants around the honorific.
    value = re.sub(r"\bآی\s+دکتر\b", "آقای دکتر", value)
    return value


def _looks_like_direct_doctor_address(row: dict[str, object]) -> bool:
    start = float(row["start"])
    if start > EARLY_IDENTITY_WINDOW_SECONDS:
        return False
    text = _identity_normalized(str(row.get("text") or ""))
    explicit_name = re.search(r"(?:آقای\s+)?دکتر(?:\s+کمیل)?\s+رودی", text)
    early_greeting = re.search(
        r"(?:آقای\s+)?دکتر.{0,30}(?:خوش\s*آمد|خوش\s*اومد|سلام|در\s+خدمت)",
        text,
    )
    return bool(explicit_name or early_greeting)


def _doctor_and_host_alias_candidates(
    rows: list[dict[str, object]], host: str | None
) -> tuple[list[str], list[str], list[dict[str, object]]]:
    """Infer doctor response and possible host aliases from early direct address.

    The prior implementation required the direct address to come from the one
    diarized label already selected as host and required an exact «دکتر رودی»
    spelling. That missed clear evidence when pyannote split the host voice or
    ASR rendered «دکتر» as «دفتر». We accept only early direct-address evidence
    and the immediately following different speaker; we do not identify the
    doctor by dominance alone.
    """

    doctor_candidates: list[str] = []
    host_aliases: list[str] = []
    evidence: list[dict[str, object]] = []
    for index, row in enumerate(rows):
        if not _looks_like_direct_doctor_address(row):
            continue
        address_label = str(row["label"])
        address_end = float(row["end"])
        response_label: str | None = None
        for candidate in rows[index + 1:]:
            if float(candidate["start"]) > address_end + DOCTOR_ADDRESS_WINDOW_SECONDS:
                break
            label = str(candidate["label"])
            if label != address_label:
                response_label = label
                doctor_candidates.append(label)
                break
        if host is not None and address_label != host:
            host_aliases.append(address_label)
        evidence.append({
            "address_label": address_label,
            "response_label": response_label,
            "start": row["start"],
            "text": str(row.get("text") or ""),
        })
    return sorted(set(doctor_candidates)), sorted(set(host_aliases)), evidence


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

    doctor_candidates, host_alias_candidates, identity_evidence = (
        _doctor_and_host_alias_candidates(rows, host)
    )
    doctor = doctor_candidates[0] if len(doctor_candidates) == 1 else None

    mapping: dict[str, str] = {}
    unresolved: list[str] = []
    if host is not None:
        mapping[host] = "خانم متولیان"
    if doctor is not None:
        mapping[doctor] = "دکتر کمیل رودی"
    # Pyannote can split the same host voice into more than one raw label.
    # Only alias an early label when that exact label directly addresses the
    # doctor and there is a unique doctor response candidate.
    if doctor is not None:
        for alias in host_alias_candidates:
            if alias != doctor:
                mapping[alias] = "خانم متولیان"

    participant_index = 1
    unresolved_index = 1
    for label in sorted(labels, key=lambda value: (first_start[value], -totals[value], value)):
        if label in mapping:
            continue
        if label.startswith("گوینده نامشخص"):
            mapping[label] = label
            unresolved.append(label)
            continue
        if host is None and label == labels[0]:
            mapping[label] = f"گوینده نامشخص {unresolved_index}"
            unresolved_index += 1
            unresolved.append(label)
            continue
        if doctor is None:
            mapping[label] = f"گوینده نامشخص {unresolved_index}"
            unresolved_index += 1
            unresolved.append(label)
        else:
            mapping[label] = f"شرکت‌کننده {participant_index}"
            participant_index += 1

    host_is_first = host is not None and first_start[host] == min(first_start.values())
    status = (
        "mapped"
        if host is not None and doctor is not None and not unresolved
        else "partially_unresolved"
    )
    warnings: list[str] = []
    if host is None:
        warnings.append("Host identity unresolved: no substantial diarized speaker starts near the beginning.")
    if doctor is None:
        warnings.append(
            "Doctor identity unresolved: early direct-address evidence is insufficient or ambiguous; identity was not invented."
        )

    diagnostics = {
        "episode": episode,
        "method": "conservative-opening-host-and-early-direct-doctor-response-v4",
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
            "alias_raw_labels": host_alias_candidates if doctor is not None else [],
            "resolved": host is not None,
            "is_earliest_speaker": host_is_first,
            "first_turn_seconds": round(first_duration[host], 3) if host is not None else None,
            "max_first_start_seconds": HOST_MAX_FIRST_START_SECONDS,
            "min_first_turn_seconds": HOST_MIN_FIRST_TURN_SECONDS,
        },
        "doctor_selection": {
            "raw_label": doctor,
            "candidate_raw_labels": doctor_candidates,
            "resolved": doctor is not None,
            "evidence": "early_direct_address_followed_by_response" if doctor else "insufficient_or_ambiguous",
            "address_window_seconds": DOCTOR_ADDRESS_WINDOW_SECONDS,
            "early_identity_window_seconds": EARLY_IDENTITY_WINDOW_SECONDS,
            "dominance_not_used_for_identity": True,
            "observations": identity_evidence,
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
