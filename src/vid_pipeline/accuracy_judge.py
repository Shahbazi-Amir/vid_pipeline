"""Constrained Ollama judge that can only rank existing ASR candidates."""
from __future__ import annotations

import json
import urllib.request
from pathlib import Path
from typing import Any, Callable

from vid_pipeline.accuracy import AccuracyError

Transport = Callable[[str, bytes, int], dict[str, Any]]


def _request(url: str, payload: bytes, timeout: int) -> dict[str, Any]:
    request = urllib.request.Request(
        url,
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8"))


def advise_disagreements(
    job_root: str | Path,
    *,
    model: str,
    base_url: str = "http://127.0.0.1:11434",
    timeout_seconds: int = 90,
    transport: Transport | None = None,
) -> dict[str, Any]:
    if not model.strip():
        return {"status": "disabled", "judged": 0}
    root = Path(job_root)
    disagreements_path = root / "accuracy" / "disagreements.json"
    consensus_path = root / "accuracy" / "transcript.consensus.json"
    if not disagreements_path.exists() or not consensus_path.exists():
        raise AccuracyError("accuracy package is required before advisory judging")
    payload = json.loads(disagreements_path.read_text(encoding="utf-8"))
    consensus = json.loads(consensus_path.read_text(encoding="utf-8"))
    segments = list(consensus.get("segments") or [])
    positions = {int(segment.get("id", index)): index for index, segment in enumerate(segments)}
    sender = transport or _request
    judged = failed = 0
    for item in payload.get("items") or []:
        candidates = list(item.get("candidates") or [])
        if len(candidates) < 2:
            continue
        position = positions.get(int(item["segment_id"]), -1)
        before = str(segments[position - 1].get("text") or "") if position > 0 else ""
        after = (
            str(segments[position + 1].get("text") or "")
            if 0 <= position < len(segments) - 1
            else ""
        )
        instruction = {
            "rule": (
                "You may only select one supplied candidate by zero-based index. "
                "Never rewrite, merge, correct, or invent text. When evidence is weak, return null."
            ),
            "before": before,
            "after": after,
            "candidates": [candidate.get("text") for candidate in candidates],
            "required_json": {"choice": "integer or null", "uncertain": "boolean"},
        }
        request_body = json.dumps(
            {
                "model": model,
                "stream": False,
                "format": "json",
                "messages": [
                    {
                        "role": "user",
                        "content": json.dumps(instruction, ensure_ascii=False),
                    }
                ],
                "options": {"temperature": 0},
            }
        ).encode("utf-8")
        try:
            response = sender(
                base_url.rstrip("/") + "/api/chat",
                request_body,
                timeout_seconds,
            )
            decision = json.loads(response.get("message", {}).get("content", "{}"))
            choice = decision.get("choice")
            uncertain = bool(decision.get("uncertain", False))
            valid = choice is None or (
                isinstance(choice, int) and 0 <= choice < len(candidates)
            )
            if not valid:
                choice = None
                uncertain = True
            item["llm_advisory"] = {
                "model": model,
                "choice": choice,
                "uncertain": uncertain,
                "advisory_only": True,
                "applied_to_text": False,
            }
            judged += 1
        except Exception as exc:
            item["llm_advisory"] = {
                "model": model,
                "choice": None,
                "uncertain": True,
                "advisory_only": True,
                "applied_to_text": False,
                "error": f"{type(exc).__name__}: {exc}",
            }
            failed += 1
    disagreements_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    report = {
        "status": "completed",
        "model": model,
        "judged": judged,
        "failed": failed,
        "advisory_only": True,
        "text_modified": False,
    }
    (root / "accuracy" / "judge-report.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return report


__all__ = ["advise_disagreements"]
