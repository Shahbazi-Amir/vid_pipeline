"""Queue interfaces and deployment adapters."""

from __future__ import annotations

import os
from collections.abc import Callable
from dataclasses import dataclass
from typing import Protocol

DEFAULT_JOB_TIMEOUT_SECONDS = 12 * 60 * 60
MIN_JOB_TIMEOUT_SECONDS = 5 * 60
MAX_JOB_TIMEOUT_SECONDS = 7 * 24 * 60 * 60
DEFAULT_RESULT_TTL_SECONDS = 7 * 24 * 60 * 60
DEFAULT_FAILURE_TTL_SECONDS = 30 * 24 * 60 * 60


@dataclass(frozen=True, slots=True)
class QueuePolicy:
    """Operational limits for long-running transcription jobs.

    RQ's own default runtime limit is too short for ASR.  Keep the policy
    explicit at enqueue time so a deployment cannot silently fall back to the
    RQ default after a library/configuration change.
    """

    job_timeout_seconds: int = DEFAULT_JOB_TIMEOUT_SECONDS
    result_ttl_seconds: int = DEFAULT_RESULT_TTL_SECONDS
    failure_ttl_seconds: int = DEFAULT_FAILURE_TTL_SECONDS

    @classmethod
    def from_env(cls) -> "QueuePolicy":
        def integer(name: str, default: int, minimum: int, maximum: int) -> int:
            raw = os.getenv(name, str(default)).strip()
            try:
                value = int(raw)
            except ValueError as exc:
                raise ValueError(f"{name} must be an integer number of seconds") from exc
            if not minimum <= value <= maximum:
                raise ValueError(f"{name} must be between {minimum} and {maximum} seconds")
            return value

        return cls(
            job_timeout_seconds=integer(
                "VID_PIPELINE_JOB_TIMEOUT_SECONDS",
                DEFAULT_JOB_TIMEOUT_SECONDS,
                MIN_JOB_TIMEOUT_SECONDS,
                MAX_JOB_TIMEOUT_SECONDS,
            ),
            result_ttl_seconds=integer(
                "VID_PIPELINE_RESULT_TTL_SECONDS",
                DEFAULT_RESULT_TTL_SECONDS,
                60,
                MAX_JOB_TIMEOUT_SECONDS,
            ),
            failure_ttl_seconds=integer(
                "VID_PIPELINE_FAILURE_TTL_SECONDS",
                DEFAULT_FAILURE_TTL_SECONDS,
                60,
                MAX_JOB_TIMEOUT_SECONDS,
            ),
        )


class JobQueue(Protocol):
    def enqueue(self, job_id: str) -> None: ...
    def cancel(self, job_id: str) -> None: ...


class InlineJobQueue:
    def __init__(self, callback: Callable[[str], None] | None = None) -> None:
        self.callback = callback
        self.enqueued: list[str] = []
        self.cancelled: set[str] = set()

    def enqueue(self, job_id: str) -> None:
        self.enqueued.append(job_id)
        if self.callback:
            self.callback(job_id)

    def cancel(self, job_id: str) -> None:
        self.cancelled.add(job_id)


class RedisJobQueue:
    def __init__(
        self,
        redis_url: str,
        queue_name: str = "vid-pipeline",
        *,
        policy: QueuePolicy | None = None,
    ) -> None:
        from redis import Redis
        from rq import Queue

        self.policy = policy or QueuePolicy.from_env()
        self.queue = Queue(
            queue_name,
            connection=Redis.from_url(redis_url),
            default_timeout=self.policy.job_timeout_seconds,
        )

    def enqueue(self, job_id: str) -> None:
        self.queue.enqueue(
            "vid_pipeline.server.worker.run_job_from_environment",
            job_id,
            job_id=job_id,
            job_timeout=self.policy.job_timeout_seconds,
            result_ttl=self.policy.result_ttl_seconds,
            failure_ttl=self.policy.failure_ttl_seconds,
        )

    def cancel(self, job_id: str) -> None:
        from rq.command import send_stop_job_command

        send_stop_job_command(self.queue.connection, job_id)
