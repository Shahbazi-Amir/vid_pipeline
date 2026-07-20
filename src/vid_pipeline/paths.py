"""Deterministic paths for one episode workspace."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from vid_pipeline.models import EpisodeSpec


@dataclass(frozen=True, slots=True)
class EpisodePaths:
    """Resolve all runtime and export paths for an episode."""

    root: Path
    spec: EpisodeSpec

    @property
    def episode_root(self) -> Path:
        return self.root / self.spec.collection / self.spec.episode_slug

    @property
    def state(self) -> Path:
        return self.episode_root / "state.json"

    @property
    def source_metadata(self) -> Path:
        return self.episode_root / "source.json"

    @property
    def discovery(self) -> Path:
        return self.episode_root / "discovery.json"

    @property
    def video_metadata(self) -> Path:
        return self.episode_root / "video-info.json"

    @property
    def video_dir(self) -> Path:
        return self.episode_root / "video"

    @property
    def audio(self) -> Path:
        return self.episode_root / "audio" / "audio-16k-mono.wav"

    @property
    def raw_json(self) -> Path:
        return self.episode_root / "raw" / f"{self.spec.episode_slug}.raw.json"

    @property
    def raw_markdown(self) -> Path:
        return self.episode_root / "raw" / f"{self.spec.episode_slug}.raw.md"

    @property
    def review_markdown(self) -> Path:
        return self.episode_root / "review" / f"{self.spec.episode_slug}.review.md"

    @property
    def final_markdown(self) -> Path:
        return self.episode_root / "final" / f"{self.spec.episode_slug}.md"

    @property
    def review_receipt(self) -> Path:
        return self.episode_root / "review" / "review-receipt.json"

    @property
    def rag_jsonl(self) -> Path:
        return self.episode_root / "rag" / f"{self.spec.collection}-{self.spec.episode_slug}.jsonl"

    def ensure(self) -> None:
        for path in {
            self.episode_root,
            self.video_dir,
            self.audio.parent,
            self.raw_json.parent,
            self.review_markdown.parent,
            self.final_markdown.parent,
            self.rag_jsonl.parent,
        }:
            path.mkdir(parents=True, exist_ok=True)

    def destination_paths(self) -> dict[str, str]:
        return {
            "source": f"sources/{self.spec.collection}/{self.spec.episode_slug}.json",
            "raw": f"raw/{self.spec.collection}/{self.spec.episode_slug}.raw.json",
            "transcript": f"transcripts/{self.spec.collection}/{self.spec.episode_slug}.md",
            "rag": f"rag/episodes/{self.spec.collection}-{self.spec.episode_slug}.jsonl",
        }
