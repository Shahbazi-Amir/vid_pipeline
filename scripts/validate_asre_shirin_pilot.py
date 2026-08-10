from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any

TIMESTAMP = re.compile(
    r"\[(\d{2}):(\d{2}):(\d{2})\s*→\s*(\d{2}):(\d{2}):(\d{2})\]\s+\*\*([^*]+)\*\*"
)
TIMESTAMP_HEADER = re.compile(
    r"(?m)^\[\d{2}:\d{2}:\d{2}\s*→\s*\d{2}:\d{2}:\d{2}\]"
)
PERSIAN = re.compile(r"[\u0600-\u06ff]")
ALLOWED_ROLE = re.compile(
    r"^(?:خانم متولیان|دکتر کمیل رودی|شرکت‌کننده \d+|گوینده نامشخص(?: \d+)?)$"
)


def _seconds(values: tuple[str, str, str]) -> int:
    return int(values[0]) * 3600 + int(values[1]) * 60 + int(values[2])


def _load(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _job_root(root: Path) -> Path:
    rows = [path.parent.parent for path in root.glob("*/raw/transcript.raw.json")]
    unique = sorted(set(rows))
    if len(unique) != 1:
        raise ValueError(f"Expected exactly one pipeline job under {root}, found {len(unique)}")
    return unique[0]


def _timeline_quality(path: Path, media_duration: float) -> dict[str, Any]:
    text = path.read_text(encoding="utf-8")
    matches = list(TIMESTAMP.finditer(text))
    timestamp_headers = list(TIMESTAMP_HEADER.finditer(text))
    rows = []
    for index, match in enumerate(matches):
        start = _seconds(match.group(1, 2, 3))
        end = _seconds(match.group(4, 5, 6))
        body_end = matches[index + 1].start() if index + 1 < len(matches) else len(text)
        body = text[match.end():body_end].strip()
        rows.append({"start": start, "end": end, "speaker": match.group(7).strip(), "text": body})
    checks: dict[str, bool] = {
        "persian_transcript": bool(PERSIAN.search(text)),
        "timestamp_rows_present": bool(rows),
        "all_timestamp_blocks_have_speaker": len(matches) == len(timestamp_headers),
        "timestamps_monotonic": all(
            row["end"] >= row["start"]
            and (index == 0 or row["start"] >= rows[index - 1]["start"])
            for index, row in enumerate(rows)
        ),
        "speaker_changes_present": any(
            rows[index]["speaker"] != rows[index - 1]["speaker"]
            for index in range(1, len(rows))
        ),
        "no_duplicate_text_across_speaker_boundaries": all(
            not (
                rows[index]["speaker"] != rows[index - 1]["speaker"]
                and re.sub(r"\s+", " ", rows[index]["text"]).strip()
                == re.sub(r"\s+", " ", rows[index - 1]["text"]).strip()
            )
            for index in range(1, len(rows))
        ),
        "timestamps_within_media": bool(rows)
        and rows[-1]["end"] <= int(media_duration) + 5,
    }
    gaps = [max(0, rows[index]["start"] - rows[index - 1]["end"]) for index in range(1, len(rows))]
    max_gap = max(gaps, default=0)
    checks["no_large_unexplained_gap"] = max_gap <= 120
    return {
        "checks": checks,
        "timestamp_block_count": len(rows),
        "speaker_change_count": sum(
            rows[index]["speaker"] != rows[index - 1]["speaker"]
            for index in range(1, len(rows))
        ),
        "max_gap_seconds": max_gap,
        "first_start_seconds": rows[0]["start"] if rows else None,
        "first_speaker": rows[0]["speaker"] if rows else None,
        "last_end_seconds": rows[-1]["end"] if rows else None,
        "speakers": sorted({row["speaker"] for row in rows}),
    }


def _stage_row(timing: dict[str, Any], prefix: str) -> float:
    return round(float(timing.get(prefix) or 0), 3)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--episode", type=int, required=True)
    parser.add_argument("--candidate-root", type=Path, required=True)
    parser.add_argument("--candidate-work-root", type=Path, required=True)
    parser.add_argument("--baseline-root", type=Path, required=True)
    parser.add_argument("--baseline-total-seconds", type=float, required=True)
    parser.add_argument("--output-json", type=Path, required=True)
    parser.add_argument("--output-markdown", type=Path, required=True)
    args = parser.parse_args()

    n = str(args.episode)
    timestamped = args.candidate_root / "timestamped" / f"{n}.md"
    role_path = args.candidate_root / "roles" / f"{n}.json"
    source_path = args.candidate_root / "sources" / f"{n}.json"
    timing_path = args.candidate_root / "timings" / f"{n}.json"
    for path in (timestamped, role_path, source_path, timing_path):
        if not path.is_file() or path.stat().st_size == 0:
            raise SystemExit(f"pilot evidence is missing: {path}")

    role = _load(role_path)
    source = _load(source_path)
    candidate = _load(timing_path)
    media = source.get("media") or {}
    media_duration = float(media.get("duration_seconds") or candidate.get("media_duration_seconds") or 0)
    timeline = _timeline_quality(timestamped, media_duration)

    mapping = role.get("mapping") or {}
    mapped_roles = list(mapping.values())
    unresolved = [value for value in mapped_roles if value.startswith("گوینده نامشخص")]
    host_opening = (
        "خانم متولیان" in mapped_roles
        and timeline["first_speaker"] == "خانم متولیان"
        and float(timeline["first_start_seconds"] or 0) <= 12
    )
    doctor_selection = role.get("doctor_selection") or {}
    role_checks = {
        "host_opening_plausibly_separated": host_opening,
        "doctor_not_inferred_from_dominance": doctor_selection.get(
            "dominance_not_used_for_identity"
        )
        is True,
        "conservative_role_status": role.get("status") in {"mapped", "partially_unresolved"},
        "distinct_role_labels": len(mapped_roles) == len(set(mapped_roles)),
        "no_hallucinated_role_names": all(ALLOWED_ROLE.fullmatch(value) for value in mapped_roles),
    }

    baseline_job = _job_root(args.baseline_root)
    baseline_raw = _load(baseline_job / "raw" / "transcript.raw.json")
    baseline_accuracy = _load(baseline_job / "accuracy" / "manifest.json")
    baseline_state = _load(baseline_job / "state.json")
    baseline_stages = baseline_state.get("stages") or {}
    baseline_audio = (baseline_stages.get("audio") or {}).get("details") or {}
    baseline_export = (baseline_stages.get("export") or {}).get("details") or {}
    baseline_raw_timing = baseline_raw.get("timing") or {}
    baseline_accuracy_timing = baseline_accuracy.get("timing") or {}
    baseline_duration = float(baseline_raw.get("duration") or 0)
    baseline_asr = float(baseline_raw_timing.get("asr_inference_seconds") or 0) + float(
        baseline_accuracy_timing.get("additional_asr_inference_seconds") or 0
    )
    baseline = {
        "setup_seconds": candidate.get("setup_seconds", 0),
        "T_resolve": 0.0,
        "T_download": 0.0,
        "T_ffprobe": 0.0,
        "T_normalize": float(baseline_audio.get("normalize_seconds") or 0),
        "T_asr_model_load": float(baseline_raw_timing.get("asr_model_load_seconds") or 0)
        + float(baseline_accuracy_timing.get("additional_asr_model_load_seconds") or 0),
        "T_asr_inference": baseline_asr,
        "T_pyannote_model_load": 0.0,
        "T_diarization_inference": 0.0,
        "T_alignment": 0.0,
        "T_role_mapping": 0.0,
        "T_export": float(baseline_export.get("export_seconds") or 0),
        "total_worker_seconds": args.baseline_total_seconds,
        "asr_rtf": round(baseline_asr / baseline_duration, 6) if baseline_duration else None,
        "transcript_segment_count": len(baseline_raw.get("segments") or []),
    }

    all_checks = {**timeline["checks"], **role_checks}
    all_checks.update(
        {
            "media_nonempty": int(media.get("media_size_bytes") or 0) > 0,
            "media_sha256_present": bool(re.fullmatch(r"[0-9a-f]{64}", str(media.get("media_sha256") or ""))),
            "media_ffprobe_duration_present": media_duration > 0,
            "run_file_handoff": source.get("compute_handoff") == "run-file",
            "automatic_speaker_count": (role.get("diarization_report") or {}).get(
                "requested_speaker_count"
            )
            is None,
            "at_least_two_effective_speakers": int(
                (role.get("diarization_report") or {}).get("aligned_effective_speaker_count")
                or 0
            )
            >= 2,
            "external_ai_disabled": source.get("external_ai_review") is False,
        }
    )
    passed = all(all_checks.values())
    stages = [
        ("setup", "setup_seconds"),
        ("resolve", "T_resolve"),
        ("download", "T_download"),
        ("normalization", "T_normalize"),
        ("ASR model load", "T_asr_model_load"),
        ("ASR inference", "T_asr_inference"),
        ("pyannote model load", "T_pyannote_model_load"),
        ("diarization", "T_diarization_inference"),
        ("alignment", "T_alignment"),
        ("role mapping", "T_role_mapping"),
        ("export", "T_export"),
        ("total worker", "total_worker_seconds"),
    ]
    report = {
        "schema_version": 1,
        "episode": args.episode,
        "gate": "PASS" if passed else "FAIL",
        "checks": all_checks,
        "media": media,
        "candidate_b": candidate,
        "baseline_c": baseline,
        "optional_d": "not_run",
        "quality": timeline,
        "diarization": {
            "raw_speaker_count": (role.get("diarization_report") or {}).get(
                "raw_speaker_count"
            ),
            "effective_speaker_count": (role.get("diarization_report") or {}).get(
                "aligned_effective_speaker_count"
            ),
            "role_mapping_status": role.get("status"),
            "unresolved_speakers": unresolved,
        },
    }
    args.output_json.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    lines = [
        f"# Asre Shirin episode {args.episode} pilot",
        "",
        f"Gate: **{report['gate']}**",
        "",
        "| Stage | Candidate B (s) | Baseline C (s) |",
        "|---|---:|---:|",
    ]
    lines.extend(
        f"| {label} | {_stage_row(candidate, key):.3f} | {_stage_row(baseline, key):.3f} |"
        for label, key in stages
    )
    lines.extend(["", "## Checks", ""])
    lines.extend(f"- {name}: {'PASS' if value else 'FAIL'}" for name, value in all_checks.items())
    args.output_markdown.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    if not passed:
        failed = [name for name, value in all_checks.items() if not value]
        raise SystemExit(f"pilot quality gate failed: {failed}")


if __name__ == "__main__":
    main()
