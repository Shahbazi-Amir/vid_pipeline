"""Environment-independent job and transcript data models."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Literal

ReviewStatus = Literal[
    "machine_transcribed",
    "machine_cleaned",
    "local_review_completed",
    "local_review_with_fallback",
    "external_review_pending",
    "human_review_required",
    "human_verified",
    "failed",
]


@dataclass(slots=True)
class JobRequest:
    job_id: str
    input_type: Literal["url", "file"]
    input_location: str
    output_location: str = "outputs"
    source_url: str = ""
    language: str = "fa"
    profile: str = "balanced"
    asr_model: str = "small"
    review_configuration: dict[str, Any] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> JobRequest:
        return cls(**value)


@dataclass(slots=True)
class TranscriptSegment:
    segment_id: int
    start: float
    end: float
    text: str
    confidence: float | None = None
    source: str = "asr"
    review_status: ReviewStatus = "machine_transcribed"
    suspicious_flags: list[str] = field(default_factory=list)
    provenance: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class TranscriptDocument:
    job_id: str
    language: str
    segments: list[TranscriptSegment]
    title: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def text(self) -> str:
        return " ".join(segment.text.strip() for segment in self.segments if segment.text.strip())

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": "1.0",
            "job_id": self.job_id,
            "language": self.language,
            "title": self.title,
            "metadata": self.metadata,
            "segments": [segment.to_dict() for segment in self.segments],
            "text": self.text,
        }
