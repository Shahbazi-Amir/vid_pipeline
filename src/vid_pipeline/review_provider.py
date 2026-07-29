"""Provider-neutral transcript review contracts."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol

from vid_pipeline.models import TranscriptDocument


@dataclass(slots=True)
class ReviewContext:
    glossary: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class ReviewResult:
    document: TranscriptDocument
    provider: str
    model: str | None = None
    warnings: list[str] = field(default_factory=list)
    usage: dict[str, Any] | None = None


class TranscriptReviewProvider(Protocol):
    def review(self, document: TranscriptDocument, context: ReviewContext) -> ReviewResult: ...


class NoOpReviewProvider:
    def review(self, document: TranscriptDocument, context: ReviewContext) -> ReviewResult:
        return ReviewResult(document=document, provider="noop")


class LocalReviewProvider(Protocol):
    """Contract for a shared local reviewer. Implementations own model lifecycle."""

    def review(self, document: TranscriptDocument, context: ReviewContext) -> ReviewResult: ...


# OpenAIReviewProvider is intentionally not implemented in this phase.
