"""Queue interfaces and deployment adapters."""

from __future__ import annotations

from collections.abc import Callable
from typing import Protocol


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
    def __init__(self, redis_url: str, queue_name: str = "vid-pipeline") -> None:
        from redis import Redis
        from rq import Queue

        self.queue = Queue(queue_name, connection=Redis.from_url(redis_url))

    def enqueue(self, job_id: str) -> None:
        self.queue.enqueue(
            "vid_pipeline.server.worker.run_job_from_environment", job_id, job_id=job_id
        )

    def cancel(self, job_id: str) -> None:
        from rq.command import send_stop_job_command

        send_stop_job_command(self.queue.connection, job_id)
