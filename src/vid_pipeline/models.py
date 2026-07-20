"""Data models used by the pipeline."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from vid_pipeline.errors import ConfigurationError


@dataclass(slots=True)
class EpisodeSpec:
    """Describe one video episode and its destination naming."""

    program: str
    collection: str
    season: str
    season_episode: int
    overall_episode: int
    speaker: str
    title: str = ""
    input_value: str = ""
    source_url: str = ""
    video_url: str = ""
    additional_speakers: list[str] = field(default_factory=list)
    search_site: str = "https://www.fintelligence.ir/"
    source_verified: bool = False
    speaker_verified: bool = False

    @property
    def episode_slug(self) -> str:
        return f"episode-{self.season_episode:02d}"

    @property
    def record_id(self) -> str:
        return f"{self.collection}-{self.season_episode:02d}"

    @property
    def commit_message(self) -> str:
        if self.collection == "asre-shirin-season-2":
            return f"Review Asre Shirin season 2 episode {self.season_episode:02d}"
        return f"Review {self.collection} episode {self.season_episode:02d}"

    @property
    def speakers(self) -> list[str]:
        values = [self.speaker, *self.additional_speakers]
        return list(dict.fromkeys(value.strip() for value in values if value.strip()))

    def validate(self) -> None:
        required = {
            "program": self.program,
            "collection": self.collection,
            "season": self.season,
            "speaker": self.speaker,
        }
        missing = [name for name, value in required.items() if not str(value).strip()]
        if missing:
            raise ConfigurationError(f"Missing required fields: {', '.join(missing)}")
        if self.season_episode < 1 or self.overall_episode < 1:
            raise ConfigurationError("Episode numbers must be positive integers.")
        if "/" in self.collection or "\\" in self.collection:
            raise ConfigurationError("Collection must be a safe folder name.")
        if self.search_site and urlparse(self.search_site).scheme not in {"http", "https"}:
            raise ConfigurationError("search_site must use http or https.")
        for name in ("source_url", "video_url"):
            value = getattr(self, name)
            if value and urlparse(value).scheme not in {"http", "https"}:
                raise ConfigurationError(f"{name} must use http or https.")

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "EpisodeSpec":
        spec = cls(**data)
        spec.validate()
        return spec

    @classmethod
    def load(cls, path: str | Path) -> "EpisodeSpec":
        data = json.loads(Path(path).read_text(encoding="utf-8"))
        return cls.from_dict(data)

    def save(self, path: str | Path) -> Path:
        self.validate()
        destination = Path(path)
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(
            json.dumps(self.to_dict(), ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        return destination


@dataclass(slots=True)
class StageRecord:
    """Persist the state of a single processing stage."""

    status: str = "pending"
    updated_at: str = ""
    output_paths: list[str] = field(default_factory=list)
    details: dict[str, Any] = field(default_factory=dict)
    error: str = ""
