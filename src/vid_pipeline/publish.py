"""Safely publish reviewed episode outputs into the transcription repository."""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path
from typing import Any

from vid_pipeline.errors import PipelineError
from vid_pipeline.models import EpisodeSpec
from vid_pipeline.paths import EpisodePaths
from vid_pipeline.rag import validate_jsonl
from vid_pipeline.review import verify_review

EXPECTED_BRANCH = "agent/financial-rag-transcripts"


def git(repo: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", "-C", str(repo), *args],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        raise PipelineError(
            result.stderr.strip() or result.stdout.strip() or "git command failed"
        )
    return result.stdout.strip()


def ensure_safe_repo(repo: Path, expected_branch: str = EXPECTED_BRANCH) -> None:
    if not (repo / ".git").exists():
        raise PipelineError(f"Not a Git repository: {repo}")
    branch = git(repo, "branch", "--show-current")
    if branch != expected_branch:
        raise PipelineError(
            f"Refusing to publish from branch '{branch}'. Expected '{expected_branch}'."
        )
    if git(repo, "status", "--porcelain"):
        raise PipelineError("Destination repository has uncommitted changes.")


def update_manifest(
    manifest_path: Path,
    spec: EpisodeSpec,
    destination_paths: dict[str, str],
    raw_data: dict[str, Any],
) -> None:
    data = (
        json.loads(manifest_path.read_text(encoding="utf-8"))
        if manifest_path.exists()
        else {}
    )
    data.setdefault("dataset", "financial-academy-transcripts")
    data.setdefault("language", "fa")
    data.setdefault("publisher", "آکادمی هوش مالی")
    programs = data.setdefault("programs", [])
    program = next(
        (
            item
            for item in programs
            if item.get("name") == spec.program and item.get("season") == spec.season
        ),
        None,
    )
    if program is None:
        program = {
            "name": spec.program,
            "season": spec.season,
            "episodes_total": 13,
            "status": "in_progress",
        }
        programs.append(program)
    episodes = data.setdefault("episodes", [])
    record = {
        "id": spec.record_id,
        "program": spec.program,
        "season": spec.season,
        "episode": spec.season_episode,
        "overall_episode": spec.overall_episode,
        "title": spec.title,
        "duration_seconds": round(float(raw_data.get("duration", 0))),
        "speakers": spec.speakers,
        "source_url": spec.source_url,
        "video_url": spec.video_url,
        "source_path": destination_paths["source"],
        "transcript_path": destination_paths["transcript"],
        "raw_path": destination_paths["raw"],
        "rag_path": destination_paths["rag"],
        "status": "reviewed",
    }
    index = next(
        (i for i, item in enumerate(episodes) if item.get("id") == spec.record_id), None
    )
    if index is None:
        episodes.append(record)
    else:
        episodes[index] = record
    data["episodes_total"] = len(episodes)
    manifest_path.write_text(
        json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )


def publish_episode(
    spec: EpisodeSpec,
    work_root: str | Path,
    destination_repo: str | Path,
    expected_branch: str = EXPECTED_BRANCH,
    push: bool = False,
    remote: str = "origin",
) -> str:
    repo = Path(destination_repo).resolve()
    ensure_safe_repo(repo, expected_branch)
    paths = EpisodePaths(Path(work_root), spec)
    verify_review(paths.final_markdown, paths.review_receipt)
    validate_jsonl(paths.rag_jsonl)
    destinations = paths.destination_paths()
    files = {
        paths.source_metadata: repo / destinations["source"],
        paths.raw_json: repo / destinations["raw"],
        paths.final_markdown: repo / destinations["transcript"],
        paths.rag_jsonl: repo / destinations["rag"],
    }
    for source, destination in files.items():
        if not source.exists():
            raise PipelineError(f"Required output is missing: {source}")
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, destination)
    raw_data = json.loads(paths.raw_json.read_text(encoding="utf-8"))
    update_manifest(repo / "manifest.json", spec, destinations, raw_data)
    relative_paths = [str(path.relative_to(repo)) for path in files.values()]
    relative_paths.append("manifest.json")
    git(repo, "add", "--", *relative_paths)
    git(repo, "commit", "-m", spec.commit_message)
    commit_sha = git(repo, "rev-parse", "HEAD")
    if push:
        git(repo, "push", remote, expected_branch)
    return commit_sha
