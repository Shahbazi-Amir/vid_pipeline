"""Stage checkpoints and timing aggregation for the Asre Shirin collection."""

from __future__ import annotations

import json
import resource
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from vid_pipeline.state import sha256_file

ASRE_SHIRIN_STAGES = (
    "media_downloaded_verified",
    "audio_normalized",
    "raw_asr_complete",
    "diarization_complete",
    "role_mapping_complete",
    "delivery_complete",
)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class AsreShirinCheckpoints:
    def __init__(self, path: Path) -> None:
        self.path = path
        self.data: dict[str, Any] = {
            "schema_version": 1,
            "updated_at": _now(),
            "stages": {
                stage: {"status": "pending", "outputs": [], "sha256": {}, "details": {}}
                for stage in ASRE_SHIRIN_STAGES
            },
        }
        if path.is_file():
            self.data = json.loads(path.read_text(encoding="utf-8"))
            for stage in ASRE_SHIRIN_STAGES:
                self.data.setdefault("stages", {}).setdefault(
                    stage,
                    {"status": "pending", "outputs": [], "sha256": {}, "details": {}},
                )

    def save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.data["updated_at"] = _now()
        temporary = self.path.with_suffix(self.path.suffix + ".tmp")
        temporary.write_text(
            json.dumps(self.data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
        temporary.replace(self.path)

    def is_complete(self, stage: str) -> bool:
        record = self.data["stages"][stage]
        if record.get("status") != "completed":
            return False
        outputs = [Path(value) for value in record.get("outputs") or []]
        if not outputs or not all(path.is_file() and path.stat().st_size > 0 for path in outputs):
            return False
        checksums = record.get("sha256") or {}
        return all(
            not checksums.get(str(path.resolve()))
            or sha256_file(path) == checksums[str(path.resolve())]
            for path in outputs
        )

    def mark_complete(
        self, stage: str, outputs: list[Path], details: dict[str, Any] | None = None
    ) -> None:
        if stage not in ASRE_SHIRIN_STAGES:
            raise KeyError(stage)
        resolved = [str(path.resolve()) for path in outputs]
        checksums = {
            str(path.resolve()): sha256_file(path)
            for path in outputs
            if path.is_file()
        }
        self.data["stages"][stage] = {
            "status": "completed",
            "updated_at": _now(),
            "outputs": resolved,
            "sha256": checksums,
            "details": details or {},
            "error": "",
        }
        self.save()

    def mark_failed(self, stage: str, error: BaseException | str) -> None:
        if stage not in ASRE_SHIRIN_STAGES:
            raise KeyError(stage)
        record = self.data["stages"][stage]
        record.update(
            status="failed",
            updated_at=_now(),
            error=f"{type(error).__name__}" if isinstance(error, BaseException) else str(error),
        )
        self.save()


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8")) if path.is_file() else {}


def collect_timing(
    job_root: Path,
    ingest: dict[str, Any],
    *,
    role_mapping_seconds: float,
    artifact_prepare_seconds: float,
    total_worker_seconds: float,
) -> dict[str, Any]:
    state = _read_json(job_root / "state.json")
    stages = state.get("stages") or {}
    raw = _read_json(job_root / "raw" / "transcript.raw.json")
    accuracy = _read_json(job_root / "accuracy" / "manifest.json")
    diarization = _read_json(job_root / "diarization" / "diarization.json")
    raw_timing = raw.get("timing") or {}
    accuracy_timing = accuracy.get("timing") or {}
    diar_timing = diarization.get("timing") or {}
    audio_details = (stages.get("audio") or {}).get("details") or {}
    export_details = (stages.get("export") or {}).get("details") or {}
    setup = float(__import__("os").getenv("ASRE_SHIRIN_SETUP_SECONDS", "0") or 0)
    peak_rss = float(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss) / 1024.0
    duration = float(raw.get("duration") or ingest.get("duration_seconds") or 0)
    asr_inference = float(raw_timing.get("asr_inference_seconds") or 0) + float(
        accuracy_timing.get("additional_asr_inference_seconds") or 0
    )
    return {
        "schema_version": 1,
        "setup_seconds": round(setup, 6),
        "T_resolve": float(ingest.get("resolve_seconds") or 0),
        "T_download": float(ingest.get("download_seconds") or 0),
        "download_bytes": int(ingest.get("media_size_bytes") or 0),
        "download_mib_per_second": float(ingest.get("download_mib_per_second") or 0),
        "T_ffprobe": float(ingest.get("ffprobe_seconds") or 0),
        "T_normalize": float(audio_details.get("normalize_seconds") or 0),
        "T_asr_model_load": float(raw_timing.get("asr_model_load_seconds") or 0)
        + float(accuracy_timing.get("additional_asr_model_load_seconds") or 0),
        "T_asr_inference": asr_inference,
        "T_pyannote_model_load": float(diar_timing.get("pyannote_model_load_seconds") or 0),
        "T_diarization_inference": float(
            diar_timing.get("diarization_inference_seconds") or 0
        ),
        "T_alignment": float(diar_timing.get("alignment_seconds") or 0),
        "T_role_mapping": round(role_mapping_seconds, 6),
        "T_export": float(export_details.get("export_seconds") or 0),
        "T_artifact_prepare": round(artifact_prepare_seconds, 6),
        "total_worker_seconds": round(total_worker_seconds, 6),
        "peak_rss_mib": round(peak_rss, 3),
        "media_duration_seconds": duration,
        "asr_rtf": round(asr_inference / duration, 6) if duration > 0 else None,
        "transcript_segment_count": len(raw.get("segments") or []),
        "raw_speaker_count": diarization.get("raw_speaker_count")
        or len(diarization.get("raw_speakers") or []),
        "effective_aligned_speaker_count": diarization.get(
            "aligned_effective_speaker_count"
        ),
        "reused_verified_media": bool(ingest.get("reused_verified_media")),
    }
