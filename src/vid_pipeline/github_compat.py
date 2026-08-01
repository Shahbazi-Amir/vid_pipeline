"""GitHub client compatibility for workflow dispatches."""
from __future__ import annotations

import json
import os
import time
import uuid
from datetime import UTC, datetime
from email.utils import parsedate_to_datetime
from pathlib import Path
from typing import Any

from vid_pipeline.github_client import (
    CLOCK_SKEW_TOLERANCE,
    URL_WORKFLOW,
    GitHubClient,
    detect_repository,
)


class CompatibleGitHubClient(GitHubClient):
    """GitHub client with bounded dispatch inputs and useful HTTP errors."""

    @staticmethod
    def _error_message(exc: Exception) -> str:
        response = getattr(exc, "response", None)
        if response is None:
            return f"GitHub API request failed: {type(exc).__name__}"

        status = getattr(response, "status_code", "unknown")
        detail = ""
        try:
            payload = response.json()
            if isinstance(payload, dict):
                detail = str(payload.get("message", "")).strip()
                errors = payload.get("errors")
                if errors:
                    rendered = json.dumps(errors, ensure_ascii=False)
                    detail = f"{detail}; errors={rendered}" if detail else rendered
        except Exception:
            detail = ""

        if not detail:
            try:
                detail = str(response.text).strip()
            except Exception:
                detail = ""

        suffix = f": {detail[:1000]}" if detail else ""
        return f"GitHub API request failed: HTTP {status}{suffix}"

    def _request(self, method: str, url: str, **kwargs: Any) -> Any:
        last_error: Exception | None = None
        for attempt in range(self.retries + 1):
            try:
                response = self.http.request(method, url, **kwargs)
                response.raise_for_status()
                return response
            except Exception as exc:
                last_error = exc
                response = getattr(exc, "response", None)
                status = getattr(response, "status_code", None)
                retryable = status is None or status in {408, 429} or status >= 500
                if attempt >= self.retries or not retryable:
                    raise RuntimeError(self._error_message(exc)) from None
                time.sleep(min(2**attempt, 4))
        raise RuntimeError(self._error_message(last_error or RuntimeError("unknown error")))

    @staticmethod
    def _record_server_date(request: Any, response: Any) -> None:
        server_date = response.headers.get("Date", "")
        if not server_date:
            request.dispatch_server_at = ""
            return
        try:
            parsed = parsedate_to_datetime(server_date)
            if parsed.tzinfo is None:
                parsed = parsed.replace(tzinfo=UTC)
            request.dispatch_server_at = parsed.astimezone(UTC).isoformat()
        except (TypeError, ValueError, OverflowError):
            request.dispatch_server_at = ""

    def create_file_request(self, path: Path):
        request = super().create_file_request(path)
        if request.status not in {"workflow_succeeded", "validated", "completed"}:
            return request

        resolved = Path(path).resolve()
        fresh = type(request)(
            request_id=uuid.uuid4().hex,
            local_path=str(resolved),
            original_name=resolved.name,
            safe_asset_name=request.safe_asset_name,
            file_size=request.file_size,
            sha256=request.sha256,
        )
        self.state.save(fresh)
        return fresh

    def dispatch_upload(self, request: Any, options: dict[str, Any]) -> None:
        super().dispatch_upload(request, options)

    def dispatch_url(self, url: str, request: Any, options: dict[str, Any]) -> None:
        request.workflow_name = URL_WORKFLOW
        request.dispatch_id = uuid.uuid4().hex
        request.dispatch_started_at = datetime.now(UTC).isoformat()
        request.status = "dispatching"
        request.workflow_started_at = request.dispatch_started_at
        self.state.save(request)
        response = self._request(
            "POST",
            self._repo_url(f"/actions/workflows/{URL_WORKFLOW}/dispatches"),
            json={
                "ref": self.ref,
                "inputs": {
                    "url": url,
                    "request_id": request.request_id,
                    "dispatch_id": request.dispatch_id,
                    "whisper_model": options.get("model", "small"),
                    "language": options.get("language", "fa"),
                    "no_editorial": str(options.get("no_editorial", True)).lower(),
                    "audio_profile": options.get("audio_profile", "safe"),
                },
            },
        )
        self._record_server_date(request, response)
        if response.content:
            try:
                request.workflow_run_id = int(response.json().get("workflow_run_id", 0))
            except (TypeError, ValueError, json.JSONDecodeError):
                pass
        request.status = "queued"
        self.state.save(request)

    def find_run(self, request: Any) -> dict[str, Any] | None:
        if request.workflow_name != URL_WORKFLOW:
            return super().find_run(request)
        if request.workflow_run_id:
            return self._request(
                "GET", self._repo_url(f"/actions/runs/{request.workflow_run_id}")
            ).json()
        if not request.dispatch_id or not request.dispatch_started_at:
            return None
        runs = self._request(
            "GET",
            self._repo_url(f"/actions/workflows/{request.workflow_name}/runs"),
            params={"event": "workflow_dispatch", "branch": self.ref, "per_page": 50},
        ).json().get("workflow_runs", [])
        reference_time = request.dispatch_server_at or request.dispatch_started_at
        try:
            dispatched_at = datetime.fromisoformat(reference_time.replace("Z", "+00:00"))
        except ValueError:
            return None
        earliest_allowed = dispatched_at - CLOCK_SKEW_TOLERANCE
        expected_title = f"Video URL {request.request_id} — attempt {request.dispatch_id}"
        for run in runs:
            created_at = str(run.get("created_at", ""))
            try:
                created = datetime.fromisoformat(created_at.replace("Z", "+00:00"))
            except ValueError:
                continue
            workflow_path = str(run.get("path", "")).split("@", 1)[0]
            if (
                run.get("event") != "workflow_dispatch"
                or run.get("head_branch") != self.ref
                or Path(workflow_path).name != request.workflow_name
                or run.get("display_title") != expected_title
                or created < earliest_allowed
            ):
                continue
            request.workflow_run_id = int(run["id"])
            request.workflow_run_url = run.get("html_url", "")
            self.state.save(request)
            return run
        return None


def client_from_args(args: Any) -> CompatibleGitHubClient:
    token = os.getenv("VID_PIPELINE_GITHUB_TOKEN", "")
    repository = getattr(args, "repo", "") or detect_repository()
    ref = getattr(args, "ref", "") or os.getenv("VID_PIPELINE_GITHUB_REF", "main")
    return CompatibleGitHubClient(
        token,
        repository,
        ref=ref,
        output_root=Path(args.output_root),
    )
