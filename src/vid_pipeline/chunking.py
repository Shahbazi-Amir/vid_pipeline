"""Deterministic overlapping chunk planning."""

from __future__ import annotations

import hashlib
from dataclasses import asdict, dataclass
from pathlib import Path


@dataclass(frozen=True, slots=True)
class ChunkPlan:
    start: float
    end: float
    duration: float
    overlap_before: float
    overlap_after: float
    chunk_index: int
    source_duration: float
    source_hash: str

    def to_dict(self) -> dict[str, float | int | str]:
        return asdict(self)


def source_sha256(path: str | Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def plan_chunks(
    source_duration: float,
    *,
    chunk_duration: float = 600.0,
    overlap: float = 15.0,
    source_hash: str = "",
) -> list[ChunkPlan]:
    if source_duration <= 0 or chunk_duration <= 0:
        raise ValueError("durations must be positive")
    if overlap < 0 or overlap >= chunk_duration:
        raise ValueError("overlap must satisfy 0 <= overlap < chunk_duration")
    plans: list[ChunkPlan] = []
    cursor = 0.0
    index = 0
    while cursor < source_duration:
        start = max(0.0, cursor - (overlap if index else 0.0))
        nominal_end = min(source_duration, cursor + chunk_duration)
        end = min(source_duration, nominal_end + (overlap if nominal_end < source_duration else 0.0))
        plans.append(
            ChunkPlan(
                start=start,
                end=end,
                duration=end - start,
                overlap_before=cursor - start,
                overlap_after=end - nominal_end,
                chunk_index=index,
                source_duration=source_duration,
                source_hash=source_hash,
            )
        )
        cursor = nominal_end
        index += 1
    return plans


def validate_chunk_plans(plans: list[ChunkPlan]) -> None:
    if not plans:
        raise ValueError("chunk plan is empty")
    for expected, plan in enumerate(plans):
        if plan.chunk_index != expected:
            raise ValueError("chunk indexes must be continuous and unique")
        if plan.start < 0 or plan.end <= plan.start:
            raise ValueError("invalid chunk timestamp")
        if plan.end > plan.source_duration + 0.001:
            raise ValueError("chunk exceeds source duration")
