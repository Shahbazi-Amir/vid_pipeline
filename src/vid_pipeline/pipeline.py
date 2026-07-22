"""High-level resume-safe episode pipeline."""

from __future__ import annotations

import json
from collections.abc import Callable
from pathlib import Path
from typing import Any

from vid_pipeline.audio import normalize_audio, validate_normalized_audio
from vid_pipeline.download import download_video, extract_metadata
from vid_pipeline.errors import PipelineError
from vid_pipeline.models import EpisodeSpec
from vid_pipeline.paths import EpisodePaths
from vid_pipeline.review import create_review_package
from vid_pipeline.source import (
    SourceCandidate,
    discover_site,
    is_http_url,
    save_candidates,
    validate_source,
)
from vid_pipeline.state import PipelineState
from vid_pipeline.transcribe import TranscriptionConfig, transcribe_audio


class EpisodePipeline:
    """Run automatic stages until human review is required."""

    def __init__(self, spec: EpisodeSpec, work_root: str | Path = "work") -> None:
        spec.validate()
        self.spec = spec
        self.paths = EpisodePaths(Path(work_root), spec)
        self.paths.ensure()
        self.state = PipelineState(self.paths.state)

    def _run_stage(
        self,
        name: str,
        action: Callable[[], tuple[list[Path], dict[str, Any]]],
        force: bool = False,
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

    def resolve_source(self, force: bool = False) -> dict[str, Any]:
        def action() -> tuple[list[Path], dict[str, Any]]:
            value = self.spec.video_url or self.spec.source_url or self.spec.input_value
            if not value:
                raise PipelineError("Episode has no input URL or search query.")
            candidate: SourceCandidate
            if is_http_url(value):
                candidate = validate_source(value, self.spec.title)
            else:
                candidates = discover_site(self.spec.search_site, value)
                save_candidates(candidates, self.paths.discovery)
                usable = [item for item in candidates if len(item.video_urls) == 1]
                if len(usable) != 1:
                    raise PipelineError(
                        f"Discovery found {len(usable)} unambiguous candidates. "
                        f"Review {self.paths.discovery} and set source_url/video_url explicitly."
                    )
                candidate = usable[0]
            if not self.spec.source_url:
                self.spec.source_url = candidate.page_url
            if not self.spec.video_url:
                if len(candidate.video_urls) != 1:
                    raise PipelineError(
                        "Could not select one video automatically. Inspect discovery results and set video_url."
                    )
                self.spec.video_url = candidate.video_urls[0]
            metadata = extract_metadata(self.spec.video_url)
            if not self.spec.title:
                self.spec.title = str(metadata.get("title") or candidate.title or self.spec.program)
            payload = {
                "page": candidate.to_dict(),
                "video": metadata,
                "episode": self.spec.to_dict(),
            }
            self.paths.source_metadata.write_text(
                json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )
            return [self.paths.source_metadata], {
                "source_url": self.spec.source_url,
                "video_url": self.spec.video_url,
                "title": self.spec.title,
            }

        return self._run_stage("source", action, force)

    def download(self, force: bool = False) -> dict[str, Any]:
        def action() -> tuple[list[Path], dict[str, Any]]:
            if not self.spec.source_verified or not self.spec.speaker_verified:
                raise PipelineError(
                    "Refusing to download until source_verified and speaker_verified are true in the episode spec."
                )
            video, metadata = download_video(self.spec.video_url, self.paths.video_dir)
            return [video, self.paths.video_metadata], {
                "video_path": str(video),
                "duration": metadata.get("duration"),
                "extractor": metadata.get("extractor_key") or metadata.get("extractor"),
            }

        return self._run_stage("download", action, force)

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

    def audio(self, force: bool = False) -> dict[str, Any]:
        def action() -> tuple[list[Path], dict[str, Any]]:
            video = self._downloaded_video()
            normalized = normalize_audio(video, self.paths.audio, overwrite=force)
            probe = validate_normalized_audio(normalized)
            return [normalized], {"probe": probe}

        return self._run_stage("audio", action, force)

    def transcribe(
        self,
        config: TranscriptionConfig | None = None,
        force: bool = False,
    ) -> dict[str, Any]:
        def action() -> tuple[list[Path], dict[str, Any]]:
            result = transcribe_audio(
                self.paths.audio,
                self.paths.raw_json,
                self.paths.raw_markdown,
                config,
            )
            flagged = sum(bool(item.get("review_flags")) for item in result.get("segments", []))
            return [self.paths.raw_json, self.paths.raw_markdown], {
                "duration": result.get("duration"),
                "segments": len(result.get("segments", [])),
                "flagged_segments": flagged,
                "model": result.get("model"),
                "device": result.get("device"),
            }

        return self._run_stage("transcribe", action, force)

    def review_package(self, force: bool = False) -> dict[str, Any]:
        def action() -> tuple[list[Path], dict[str, Any]]:
            path = create_review_package(
                self.spec, self.paths.raw_json, self.paths.review_markdown
            )
            return [path], {"review_file": str(path)}

        result = self._run_stage("review_package", action, force)
        self.state.stage("review").update(
            status="review_required",
            error="",
            output_paths=[str(self.paths.final_markdown.resolve())],
        )
        self.state.save()
        return result

    def run_automatic(
        self,
        config: TranscriptionConfig | None = None,
        force: bool = False,
    ) -> list[dict[str, Any]]:
        return [
            self.resolve_source(force=force),
            self.download(force=force),
            self.audio(force=force),
            self.transcribe(config=config, force=force),
            self.review_package(force=force),
        ]
