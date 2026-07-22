"""Standalone URL-to-transcript pipeline."""

from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from vid_pipeline.audio import normalize_audio, validate_normalized_audio
from vid_pipeline.clean import clean_transcript
from vid_pipeline.download import download_video, extract_metadata
from vid_pipeline.errors import PipelineError
from vid_pipeline.state import PipelineState
from vid_pipeline.transcribe import TranscriptionConfig, transcribe_audio

_SAFE_RE = re.compile(r"[^a-zA-Z0-9._-]+")


def make_job_id(url: str, name: str = "") -> str:
    """Create a stable, filesystem-safe job id from a URL and optional name."""
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise ValueError("url must be an http or https URL")
    candidate = name.strip() or Path(parsed.path.rstrip("/")).name or parsed.netloc
    candidate = _SAFE_RE.sub("-", candidate).strip("-._").lower() or "video"
    digest = hashlib.sha256(url.encode("utf-8")).hexdigest()[:8]
    return f"{candidate[:48]}-{digest}"


@dataclass(frozen=True, slots=True)
class VideoJobPaths:
    root: Path
    job_id: str

    @property
    def job_root(self) -> Path:
        return self.root / self.job_id

    @property
    def state(self) -> Path:
        return self.job_root / "state.json"

    @property
    def source_metadata(self) -> Path:
        return self.job_root / "source.json"

    @property
    def video_metadata(self) -> Path:
        return self.job_root / "video-info.json"

    @property
    def video_dir(self) -> Path:
        return self.job_root / "video"

    @property
    def audio(self) -> Path:
        return self.job_root / "audio" / "audio-16k-mono.wav"

    @property
    def raw_json(self) -> Path:
        return self.job_root / "raw" / "transcript.raw.json"

    @property
    def raw_markdown(self) -> Path:
        return self.job_root / "raw" / "transcript.raw.md"

    @property
    def final_markdown(self) -> Path:
        return self.job_root / "final" / "transcript.final.md"

    @property
    def final_text(self) -> Path:
        return self.job_root / "final" / "transcript.final.txt"

    @property
    def result(self) -> Path:
        return self.job_root / "result.json"

    def ensure(self) -> None:
        for path in {
            self.job_root,
            self.video_dir,
            self.audio.parent,
            self.raw_json.parent,
            self.final_markdown.parent,
        }:
            path.mkdir(parents=True, exist_ok=True)


class VideoPipeline:
    """Resume-safe pipeline that converts one video URL into final text files."""

    def __init__(
        self,
        url: str,
        output_root: str | Path = "outputs",
        name: str = "",
        *,
        no_check_certificate: bool = False,
    ) -> None:
        self.url = url
        self.no_check_certificate = no_check_certificate
        self.job_id = make_job_id(url, name)
        self.paths = VideoJobPaths(Path(output_root), self.job_id)
        self.paths.ensure()
        self.state = PipelineState(self.paths.state)
        self.metadata: dict[str, Any] = {}
        if self.paths.source_metadata.exists():
            self.metadata = json.loads(self.paths.source_metadata.read_text(encoding="utf-8"))

    def _run_stage(
        self,
        name: str,
        action: Callable[[], tuple[list[Path], dict[str, Any]]],
        *,
        force: bool,
    ) -> dict[str, Any]:
        if not force and self.state.is_complete(name):
            return {"stage": name, "status": "skipped", "reason": "already complete"}
        self.state.mark_running(name)
        try:
            outputs, details = action()
            self.state.mark_complete(name, outputs, details)
            return {"stage": name, "status": "completed", **details}
        except Exception as exc:
            self.state.mark_failed(name, exc)
            raise

    def inspect(self, *, force: bool = False) -> dict[str, Any]:
        def action() -> tuple[list[Path], dict[str, Any]]:
            metadata = extract_metadata(
                self.url,
                no_check_certificate=self.no_check_certificate,
            )
            payload = {
                "schema_version": 1,
                "job_id": self.job_id,
                "url": self.url,
                "title": metadata.get("title") or "",
                "duration": metadata.get("duration"),
                "extractor": metadata.get("extractor_key") or metadata.get("extractor"),
                "uploader": metadata.get("uploader") or metadata.get("channel") or "",
            }
            self.paths.source_metadata.write_text(
                json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )
            self.metadata = payload
            return [self.paths.source_metadata], payload

        return self._run_stage("source", action, force=force)

    def download(self, *, force: bool = False) -> dict[str, Any]:
        def action() -> tuple[list[Path], dict[str, Any]]:
            video, metadata = download_video(
                self.url,
                self.paths.video_dir,
                no_check_certificate=self.no_check_certificate,
            )
            return [video, self.paths.video_metadata], {
                "video_path": str(video),
                "duration": metadata.get("duration"),
            }

        return self._run_stage("download", action, force=force)

    def _downloaded_video(self) -> Path:
        record = self.state.stage("download")
        for value in record.get("output_paths", []):
            path = Path(value)
            if path.exists() and path.parent == self.paths.video_dir.resolve():
                return path
        candidates = [item for item in self.paths.video_dir.glob("video.*") if item.is_file()]
        if not candidates:
            raise PipelineError("Downloaded video was not found.")
        return candidates[0]

    def audio(self, *, force: bool = False) -> dict[str, Any]:
        def action() -> tuple[list[Path], dict[str, Any]]:
            normalized = normalize_audio(self._downloaded_video(), self.paths.audio, overwrite=force)
            return [normalized], {"probe": validate_normalized_audio(normalized)}

        return self._run_stage("audio", action, force=force)

    def transcribe(
        self,
        config: TranscriptionConfig | None = None,
        *,
        force: bool = False,
    ) -> dict[str, Any]:
        def action() -> tuple[list[Path], dict[str, Any]]:
            result = transcribe_audio(
                self.paths.audio,
                self.paths.raw_json,
                self.paths.raw_markdown,
                config,
            )
            return [self.paths.raw_json, self.paths.raw_markdown], {
                "duration": result.get("duration"),
                "segments": len(result.get("segments", [])),
                "language": result.get("language"),
                "model": result.get("model"),
                "device": result.get("device"),
            }

        return self._run_stage("transcribe", action, force=force)

    def clean(self, *, max_words: int = 90, force: bool = False) -> dict[str, Any]:
        def action() -> tuple[list[Path], dict[str, Any]]:
            if not self.metadata and self.paths.source_metadata.exists():
                self.metadata = json.loads(self.paths.source_metadata.read_text(encoding="utf-8"))
            details = clean_transcript(
                self.paths.raw_json,
                self.paths.final_markdown,
                self.paths.final_text,
                title=str(self.metadata.get("title") or ""),
                source_url=self.url,
                max_words=max_words,
            )
            result = {
                "schema_version": 1,
                "status": "completed",
                "job_id": self.job_id,
                "source_url": self.url,
                "title": self.metadata.get("title") or "",
                "final_markdown": str(self.paths.final_markdown),
                "final_text": str(self.paths.final_text),
                "note": "Machine-cleaned transcript; human audio review is recommended for sensitive publication.",
            }
            self.paths.result.write_text(
                json.dumps(result, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )
            return [self.paths.final_markdown, self.paths.final_text, self.paths.result], details

        return self._run_stage("clean", action, force=force)

    def run(
        self,
        config: TranscriptionConfig | None = None,
        *,
        max_words: int = 90,
        force: bool = False,
    ) -> list[dict[str, Any]]:
        return [
            self.inspect(force=force),
            self.download(force=force),
            self.audio(force=force),
            self.transcribe(config=config, force=force),
            self.clean(max_words=max_words, force=force),
        ]
