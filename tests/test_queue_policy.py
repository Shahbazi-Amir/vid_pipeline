from __future__ import annotations

import sys
from types import SimpleNamespace

import pytest

from vid_pipeline.server.queue import (
    DEFAULT_FAILURE_TTL_SECONDS,
    DEFAULT_JOB_TIMEOUT_SECONDS,
    DEFAULT_RESULT_TTL_SECONDS,
    QueuePolicy,
    RedisJobQueue,
)


ENV_NAMES = (
    "VID_PIPELINE_JOB_TIMEOUT_SECONDS",
    "VID_PIPELINE_RESULT_TTL_SECONDS",
    "VID_PIPELINE_FAILURE_TTL_SECONDS",
)


def test_queue_policy_defaults_are_long_job_safe(monkeypatch: pytest.MonkeyPatch) -> None:
    for name in ENV_NAMES:
        monkeypatch.delenv(name, raising=False)

    policy = QueuePolicy.from_env()

    assert policy.job_timeout_seconds == DEFAULT_JOB_TIMEOUT_SECONDS == 43_200
    assert policy.result_ttl_seconds == DEFAULT_RESULT_TTL_SECONDS == 604_800
    assert policy.failure_ttl_seconds == DEFAULT_FAILURE_TTL_SECONDS == 2_592_000


def test_queue_policy_accepts_explicit_deployment_values(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("VID_PIPELINE_JOB_TIMEOUT_SECONDS", "21600")
    monkeypatch.setenv("VID_PIPELINE_RESULT_TTL_SECONDS", "3600")
    monkeypatch.setenv("VID_PIPELINE_FAILURE_TTL_SECONDS", "7200")

    policy = QueuePolicy.from_env()

    assert policy == QueuePolicy(
        job_timeout_seconds=21_600,
        result_ttl_seconds=3_600,
        failure_ttl_seconds=7_200,
    )


@pytest.mark.parametrize(
    "name,value",
    [
        ("VID_PIPELINE_JOB_TIMEOUT_SECONDS", "179"),
        ("VID_PIPELINE_JOB_TIMEOUT_SECONDS", "not-a-number"),
        ("VID_PIPELINE_RESULT_TTL_SECONDS", "0"),
        ("VID_PIPELINE_FAILURE_TTL_SECONDS", "999999999"),
    ],
)
def test_queue_policy_rejects_unsafe_values(
    monkeypatch: pytest.MonkeyPatch, name: str, value: str
) -> None:
    for env_name in ENV_NAMES:
        monkeypatch.delenv(env_name, raising=False)
    monkeypatch.setenv(name, value)

    with pytest.raises(ValueError, match=name):
        QueuePolicy.from_env()


def test_redis_queue_sets_timeout_and_retention_on_every_job(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    observed: dict[str, object] = {}

    class FakeRedis:
        @classmethod
        def from_url(cls, url: str):
            observed["redis_url"] = url
            return "connection"

    class FakeQueue:
        def __init__(self, name: str, *, connection: object, default_timeout: int):
            observed["queue_name"] = name
            observed["connection"] = connection
            observed["default_timeout"] = default_timeout
            self.connection = connection

        def enqueue(self, *args: object, **kwargs: object):
            observed["enqueue_args"] = args
            observed["enqueue_kwargs"] = kwargs
            return SimpleNamespace(id=kwargs.get("job_id"))

    monkeypatch.setitem(sys.modules, "redis", SimpleNamespace(Redis=FakeRedis))
    monkeypatch.setitem(sys.modules, "rq", SimpleNamespace(Queue=FakeQueue))

    policy = QueuePolicy(
        job_timeout_seconds=18_000,
        result_ttl_seconds=600,
        failure_ttl_seconds=1_200,
    )
    queue = RedisJobQueue("redis://example:6379/0", policy=policy)
    queue.enqueue("job-123")

    assert observed["redis_url"] == "redis://example:6379/0"
    assert observed["queue_name"] == "vid-pipeline"
    assert observed["default_timeout"] == 18_000
    assert observed["enqueue_args"] == (
        "vid_pipeline.server.worker.run_job_from_environment",
        "job-123",
    )
    assert observed["enqueue_kwargs"] == {
        "job_id": "job-123",
        "job_timeout": 18_000,
        "result_ttl": 600,
        "failure_ttl": 1_200,
    }
