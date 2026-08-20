from __future__ import annotations

import sys
from types import SimpleNamespace

from vid_pipeline.server.queue import QueuePolicy, RedisJobQueue


def _queue(monkeypatch, status: str, observed: dict[str, object]) -> RedisJobQueue:
    class FakeRedis:
        @classmethod
        def from_url(cls, url: str):
            return "connection"

    class FakeQueue:
        def __init__(self, name: str, *, connection: object, default_timeout: int):
            self.connection = connection

    class FakeJob:
        @classmethod
        def fetch(cls, job_id: str, connection: object):
            observed["fetch"] = (job_id, connection)
            return cls()

        def get_status(self, refresh: bool = False):
            assert refresh is True
            return status

        def cancel(self):
            observed["cancel"] = True

    def stop(connection: object, job_id: str):
        observed["stop"] = (connection, job_id)

    monkeypatch.setitem(sys.modules, "redis", SimpleNamespace(Redis=FakeRedis))
    monkeypatch.setitem(sys.modules, "rq", SimpleNamespace(Queue=FakeQueue))
    monkeypatch.setitem(sys.modules, "rq.job", SimpleNamespace(Job=FakeJob))
    monkeypatch.setitem(sys.modules, "rq.command", SimpleNamespace(send_stop_job_command=stop))
    return RedisJobQueue("redis://example", policy=QueuePolicy())


def test_queued_job_uses_job_cancel(monkeypatch) -> None:
    observed: dict[str, object] = {}
    queue = _queue(monkeypatch, "queued", observed)
    queue.cancel("job-1")
    assert observed["cancel"] is True
    assert "stop" not in observed


def test_started_job_uses_stop_command(monkeypatch) -> None:
    observed: dict[str, object] = {}
    queue = _queue(monkeypatch, "started", observed)
    queue.cancel("job-2")
    assert observed["stop"] == ("connection", "job-2")
    assert "cancel" not in observed
