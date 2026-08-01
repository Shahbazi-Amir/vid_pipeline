"""Standalone URL-to-transcript pipeline."""

from __future__ import annotations

import hashlib
import json
import re
import shutil
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from vid_pipeline.audio import normalize_audio, validate_normalized_audio
from vid_pipeline.clean import clean_transcript
from vid_pipeline.download import download_video, extract_metadata
from vid_pipeline.editorial import (
    EditorialConfig,
    EditorialMetadata,
    assess_transcript_preservation,
    edit_transcript,
    raw_transcript_text,
)
from vid_pipeline.errors import PipelineError
from vid_pipeline.state import PipelineState
from vid_pipeline.transcribe import TranscriptionConfig, transcribe_audio

_SAFE_RE = re.compile(r"[^a-zA-Z0-9._-]+")


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def make_job_id(url: str, name: str = "") -> str:
    """Create a stable, filesystem-safe job id from a URL and optional name."""

    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise ValueError("url must be an http or https URL")
    candidate = name.strip() or Path(parsed.path.rstrip("/")).name or parsed.netloc
    candidate = _SAFE_RE.sub("-", candidate).strip("-._").lower() or "video"
    digest = hashlib.sha256(url.encode("utf-8")).hexdigest()[:8]
    return f"{candidate[:48]}-{digest}"


def make_file_job_id(path: str | Path, name: str = "") -> str:
    source = Path(path).resolve()
    if not source.is_file():
        raise ValueError(f"media file does not exist: {source}")
    candidate = _SAFE_RE.sub("-", (name.strip() or source.stem)).strip("-._").lower() or "media"
    identity = f"{source}:{_sha256_file(source)}"
    identity_digest = hashlib.sha256(identity.encode()).hexdigest()[:8]
    return f"{candidate[:48]}-{identity_digest}"


def _duration_text(value: Any) -> str:
    try:
        seconds = max(0, int(float(value)))
    except (TypeError, ValueError):
        return ""
    hours, remainder = divmod(seconds, 3600)
    minutes, secs = divmod(remainder, 60)
    if hours:
        return f"{hours} ساعت و {minutes} دقیقه و {secs} ثانیه"
    return f"{minutes} دقیقه و {secs} ثانیه"


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
    def audio_quality(self) -> Path:
        return self.job_root / "audio" / "audio-quality.json"

    @property
    def raw_json(self) -> Path:
        return self.job_root / "raw" / "transcript.raw.json"

    @property
    def raw_markdown(self) -> Path:
        return self.job_root / "raw" / "transcript.raw.md"

    @property
    def machine_markdown(self) -> Path:
        return self.job_root / "machine" / "transcript.machine.md"

    @property
    def machine_text(self) -> Path:
        return self.job_root / "machine" / "transcript.machine.txt"

    @property
    def final_markdown(self) -> Path:
        return self.job_root / "final" / "transcript.final.md"

    @property
    def final_text(self) -> Path:
        return self.job_root / "final" / "transcript.final.txt"

    @property
    def editorial_report(self) -> Path:
        return self.job_root / "final" / "editorial-report.json"

    @property
    def result(self) -> Path:
        return self.job_root / "result.json"

    def ensure(self) -> None:
        for path in {
            self.job_root,
            self.video_dir,
            self.audio.parent,
            self.raw_json.parent,
            self.machine_markdown.parent,
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
        audio_profile: str = "safe",
    ) -> None:
        self.url = url
        self.job_id = make_job_id(url, name)
        self.paths = VideoJobPaths(Path(output_root), self.job_id)
        self.paths.ensure()
        self.state = PipelineState(self.paths.state)
        self.audio_profile = audio_profile
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
            metadata = extract_metadata(self.url)
            payload = {
                "schema_version": 2,
                "job_id": self.job_id,
                "url": self.url,
                "title": metadata.get("title") or "",
                "duration": metadata.get("duration"),
                "extractor": metadata.get("extractor_key") or metadata.get("extractor"),
                "uploader": metadata.get("uploader") or metadata.get("channel") or "",
                "channel": metadata.get("channel") or "",
                "upload_date": metadata.get("upload_date") or "",
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
            from vid_pipeline.media import require_decodable_audio

            media_path, metadata = download_video(self.url, self.paths.video_dir)
            media = require_decodable_audio(media_path)
            if self.paths.source_metadata.exists():
                source = json.loads(self.paths.source_metadata.read_text(encoding="utf-8"))
                source["input_type"] = media["input_type"]
                source["media"] = media
                self.paths.source_metadata.write_text(
                    json.dumps(source, ensure_ascii=False, indent=2) + "\n",
                    encoding="utf-8",
                )
                self.metadata = source
            return [media_path, self.paths.video_metadata], {
                "media_path": str(media_path),
                "video_path": str(media_path),
                "input_type": media["input_type"],
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
            normalized = normalize_audio(
                self._downloaded_video(), self.paths.audio, overwrite=force,
                profile=self.audio_profile, quality_path=self.paths.audio_quality,
            )
            return [normalized, self.paths.audio_quality], {
                "probe": validate_normalized_audio(normalized),
                "audio_profile": self.audio_profile,
            }

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
                self.metadata = json.loads(
                    self.paths.source_metadata.read_text(encoding="utf-8")
                )
            details = clean_transcript(
                self.paths.raw_json,
                self.paths.machine_markdown,
                self.paths.machine_text,
                title=str(self.metadata.get("title") or ""),
                source_url=self.url,
                max_words=max_words,
            )
            details["quality"] = "machine_only"
            return [self.paths.machine_markdown, self.paths.machine_text], details

        return self._run_stage("clean", action, force=force)

    def _machine_fallback_details(self, reason: str) -> dict[str, Any]:
        if not self.paths.machine_markdown.exists() or not self.paths.machine_text.exists():
            raise PipelineError("Machine transcript is missing; cannot create a safe fallback.")

        shutil.copyfile(self.paths.machine_markdown, self.paths.final_markdown)
        shutil.copyfile(self.paths.machine_text, self.paths.final_text)
        validation = assess_transcript_preservation(
            raw_transcript_text(self.paths.raw_json),
            self.paths.final_text.read_text(encoding="utf-8"),
        )
        if not validation["accepted"]:
            raise PipelineError(
                "Machine fallback failed content-preservation validation: "
                f"{validation['reasons']}"
            )
        return {
            "status": "machine_fallback",
            "provider": "deterministic",
            "model": None,
            "fallback_used": True,
            "fallback_reason": reason,
            "final_validation": validation,
            "markdown": str(self.paths.final_markdown),
            "text": str(self.paths.final_text),
            "human_audio_verification": False,
        }

    def editorial(
        self,
        config: EditorialConfig,
        metadata: EditorialMetadata | None = None,
        *,
        force: bool = False,
    ) -> dict[str, Any]:
        def action() -> tuple[list[Path], dict[str, Any]]:
            if not self.metadata and self.paths.source_metadata.exists():
                self.metadata = json.loads(
                    self.paths.source_metadata.read_text(encoding="utf-8")
                )
            supplied = metadata or EditorialMetadata()
            resolved = EditorialMetadata(
                title=supplied.title or str(self.metadata.get("title") or ""),
                source_url=supplied.source_url or self.url,
                program=supplied.program,
                network=supplied.network or str(self.metadata.get("uploader") or ""),
                date=supplied.date or str(self.metadata.get("upload_date") or ""),
                guest=supplied.guest,
                duration=supplied.duration or _duration_text(self.metadata.get("duration")),
                speakers=list(supplied.speakers),
                context=supplied.context,
            )

            try:
                details = edit_transcript(
                    self.paths.raw_json,
                    self.paths.final_markdown,
                    self.paths.final_text,
                    metadata=resolved,
                    config=config,
                )
            except Exception as exc:
                details = self._machine_fallback_details(
                    f"editorial_stage_error: {type(exc).__name__}: {exc}"
                )

            final_validation = dict(details.get("final_validation") or {})
            if not final_validation:
                final_validation = assess_transcript_preservation(
                    raw_transcript_text(self.paths.raw_json),
                    self.paths.final_text.read_text(encoding="utf-8"),
                )
            if not final_validation["accepted"]:
                details = self._machine_fallback_details(
                    "editorial_output_failed_full_transcript_validation"
                )
                final_validation = dict(details["final_validation"])
            else:
                details["final_validation"] = final_validation

            if not final_validation["accepted"]:
                raise PipelineError(
                    "Final transcript failed content-preservation validation after fallback."
                )

            fallback_used = bool(details.get("fallback_used"))
            if details.get("status") == "machine_fallback":
                review_status = "machine_fallback"
            elif fallback_used:
                review_status = "ai_editorial_with_machine_fallback"
            else:
                review_status = "ai_editorial_completed"

            self.paths.editorial_report.write_text(
                json.dumps(details, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )
            result = {
                "schema_version": 3,
                "status": "completed_with_fallback" if fallback_used else "completed",
                "review_status": review_status,
                "job_id": self.job_id,
                "source_url": self.url,
                "title": resolved.title,
                "machine_markdown": str(self.paths.machine_markdown),
                "machine_text": str(self.paths.machine_text),
                "final_markdown": str(self.paths.final_markdown),
                "final_text": str(self.paths.final_text),
                "editorial_report": str(self.paths.editorial_report),
                "content_preservation": final_validation,
                "human_audio_verification": False,
            }
            self.paths.result.write_text(
                json.dumps(result, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )
            return [
                self.paths.final_markdown,
                self.paths.final_text,
                self.paths.editorial_report,
                self.paths.result,
            ], details

        return self._run_stage("editorial", action, force=force)

    def finalize_machine_only(self, *, force: bool = False) -> dict[str, Any]:
        def action() -> tuple[list[Path], dict[str, Any]]:
            shutil.copyfile(self.paths.machine_markdown, self.paths.final_markdown)
            shutil.copyfile(self.paths.machine_text, self.paths.final_text)
            validation = assess_transcript_preservation(
                raw_transcript_text(self.paths.raw_json),
                self.paths.final_text.read_text(encoding="utf-8"),
            )
            if not validation["accepted"]:
                raise PipelineError(
                    "Machine-only final transcript failed content-preservation validation."
                )
            result = {
                "schema_version": 3,
                "status": "completed",
                "review_status": "machine_only",
                "job_id": self.job_id,
                "source_url": self.url,
                "final_markdown": str(self.paths.final_markdown),
                "final_text": str(self.paths.final_text),
                "content_preservation": validation,
                "warning": "Editorial stage was disabled; this is not a reviewed transcript.",
            }
            self.paths.result.write_text(
                json.dumps(result, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )
            return [self.paths.final_markdown, self.paths.final_text, self.paths.result], result

        return self._run_stage("finalize_machine", action, force=force)

    def run(
        self,
        config: TranscriptionConfig | None = None,
        *,
        editorial_config: EditorialConfig | None = None,
        editorial_metadata: EditorialMetadata | None = None,
        max_words: int = 90,
        force: bool = False,
    ) -> list[dict[str, Any]]:
        results = [
            self.inspect(force=force),
            self.download(force=force),
            self.audio(force=force),
            self.transcribe(config=config, force=force),
            self.clean(max_words=max_words, force=force),
        ]
        if editorial_config is None:
            results.append(self.finalize_machine_only(force=force))
        else:
            results.append(self.editorial(editorial_config, editorial_metadata, force=force))
        return results


class LocalMediaPipeline(VideoPipeline):
    """Run the canonical pipeline for an existing local media file."""

    def __init__(
        self,
        media_path: str | Path,
        output_root: str | Path = "outputs",
        name: str = "",
        audio_profile: str = "safe",
    ) -> None:
        self.media_path = Path(media_path).resolve()
        if not self.media_path.is_file():
            raise ValueError(f"media file does not exist: {self.media_path}")
        self.url = ""
        self.job_id = make_file_job_id(self.media_path, name)
        self.paths = VideoJobPaths(Path(output_root), self.job_id)
        self.paths.ensure()
        self.state = PipelineState(self.paths.state)
        self.audio_profile = audio_profile
        self.metadata = {}
        if self.paths.source_metadata.exists():
            self.metadata = json.loads(self.paths.source_metadata.read_text(encoding="utf-8"))

    def inspect(self, *, force: bool = False) -> dict[str, Any]:
        def action() -> tuple[list[Path], dict[str, Any]]:
            from vid_pipeline.media import require_decodable_audio

            media = require_decodable_audio(self.media_path)
            payload = {
                "schema_version": 2,
                "job_id": self.job_id,
                "input_type": media["input_type"],
                "path": str(self.media_path),
                "title": self.media_path.stem,
                "size": self.media_path.stat().st_size,
                "sha256": _sha256_file(self.media_path),
                "media": media,
            }
            self.paths.source_metadata.write_text(
                json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
            )
            self.metadata = payload
            return [self.paths.source_metadata], payload

        return self._run_stage("source", action, force=force)

    def download(self, *, force: bool = False) -> dict[str, Any]:
        def action() -> tuple[list[Path], dict[str, Any]]:
            return [self.media_path], {"media_path": str(self.media_path), "downloaded": False}

        return self._run_stage("download", action, force=force)

    def _downloaded_video(self) -> Path:
        return self.media_path
