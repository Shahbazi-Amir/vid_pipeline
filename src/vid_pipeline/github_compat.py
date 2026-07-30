"""GitHub client compatibility for workflow dispatches."""
from __future__ import annotations

import json
import os
import time
from pathlib import Path
from typing import Any

from vid_pipeline.github_client import GitHubClient, UPLOAD_WORKFLOW, _now, detect_repository


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

    def dispatch_upload(self, request: Any, options: dict[str, Any]) -> None:
        request.status = "dispatching"
        request.workflow_started_at = _now()
        self.state.save(request)
        inputs = {
            "request_id": request.request_id,
            "asset_id": str(request.asset_id),
            "asset_name": request.safe_asset_name,
            "original_name": request.original_name,
            "file_size": str(request.file_size),
            "sha256": request.sha256,
            "profile": options.get("profile", "balanced"),
            "model": options.get("model", "small"),
            "language": options.get("language", "fa"),
            "no_editorial": str(options.get("no_editorial", True)).lower(),
        }
        response = self._request(
            "POST",
            self._repo_url(f"/actions/workflows/{UPLOAD_WORKFLOW}/dispatches"),
            json={"ref": self.ref, "inputs": inputs},
        )
        if response.content:
            try:
                request.workflow_run_id = int(response.json().get("workflow_run_id", 0))
            except (TypeError, ValueError, json.JSONDecodeError):
                pass
        request.status = "queued"
        self.state.save(request)


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
