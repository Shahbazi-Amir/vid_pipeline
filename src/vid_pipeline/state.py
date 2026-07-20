"""Resume-safe state management."""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from vid_pipeline.models import StageRecord

STAGES = ("source", "download", "audio", "transcribe", "review_package", "review", "rag")


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def sha256_file(path: str | Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


class PipelineState:
    """Read and update an episode state file atomically."""

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        self.data: dict[str, Any] = {
            "schema_version": 1,
            "updated_at": utc_now(),
            "stages": {stage: asdict(StageRecord()) for stage in STAGES},
        }
        if self.path.exists():
            self.data = json.loads(self.path.read_text(encoding="utf-8"))
            for stage in STAGES:
                self.data.setdefault("stages", {}).setdefault(stage, asdict(StageRecord()))

    def save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.data["updated_at"] = utc_now()
        temporary = self.path.with_suffix(".tmp")
        temporary.write_text(
            json.dumps(self.data, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        temporary.replace(self.path)

    def stage(self, name: str) -> dict[str, Any]:
        if name not in STAGES:
            raise KeyError(f"Unknown stage: {name}")
        return self.data["stages"][name]

    def is_complete(self, name: str) -> bool:
        record = self.stage(name)
        if record.get("status") not in {"completed", "reviewed"}:
            return False
        paths = [Path(path) for path in record.get("output_paths", [])]
        return bool(paths) and all(path.exists() for path in paths)

    def mark_running(self, name: str) -> None:
        self.data["stages"][name] = {
            "status": "running",
            "updated_at": utc_now(),
            "output_paths": [],
            "details": {},
            "error": "",
        }
        self.save()

    def mark_complete(
        self,
        name: str,
        outputs: list[str | Path],
        details: dict[str, Any] | None = None,
        status: str = "completed",
    ) -> None:
        output_paths = [str(Path(path).resolve()) for path in outputs]
        checksums = {
            str(Path(path).resolve()): sha256_file(path)
            for path in outputs
            if Path(path).is_file()
        }
        self.data["stages"][name] = {
            "status": status,
            "updated_at": utc_now(),
            "output_paths": output_paths,
            "details": {**(details or {}), "sha256": checksums},
            "error": "",
        }
        self.save()

    def mark_failed(self, name: str, error: Exception | str) -> None:
        record = self.stage(name)
        record.update(status="failed", updated_at=utc_now(), error=str(error))
        self.save()
