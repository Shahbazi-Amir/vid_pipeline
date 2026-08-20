"""Persistent upload and revisioned job repository for SQLite or PostgreSQL."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import Any, Iterable

from sqlalchemy import Column, MetaData, String, Table, Text, create_engine, select
from sqlalchemy.engine import Engine


def now() -> str:
    return datetime.now(UTC).isoformat()


class ConcurrentUpdateError(RuntimeError):
    """Raised when a stale job snapshot tries to overwrite newer state."""


class Repository:
    def __init__(self, database_url: str) -> None:
        connect_args = {"check_same_thread": False} if database_url.startswith("sqlite") else {}
        self.engine: Engine = create_engine(database_url, connect_args=connect_args)
        metadata = MetaData()
        self.uploads = Table(
            "uploads", metadata,
            Column("upload_id", String(64), primary_key=True),
            Column("sha256", String(64), unique=True, nullable=False),
            Column("payload", Text, nullable=False),
        )
        self.job_table = Table(
            "jobs", metadata,
            Column("job_id", String(64), primary_key=True),
            Column("payload", Text, nullable=False),
        )
        metadata.create_all(self.engine)

    def put_upload(self, value: dict[str, Any]) -> None:
        with self.engine.begin() as db:
            existing = db.execute(
                select(self.uploads.c.upload_id).where(self.uploads.c.upload_id == value["upload_id"])
            ).first()
            payload = json.dumps(value)
            if existing:
                db.execute(
                    self.uploads.update().where(
                        self.uploads.c.upload_id == value["upload_id"]
                    ).values(sha256=value["sha256"], payload=payload)
                )
            else:
                db.execute(self.uploads.insert().values(
                    upload_id=value["upload_id"], sha256=value["sha256"], payload=payload
                ))

    def upload(self, upload_id: str) -> dict[str, Any] | None:
        with self.engine.connect() as db:
            row = db.execute(
                select(self.uploads.c.payload).where(self.uploads.c.upload_id == upload_id)
            ).first()
        return json.loads(row.payload) if row else None

    def upload_by_hash(self, digest: str) -> dict[str, Any] | None:
        with self.engine.connect() as db:
            row = db.execute(
                select(self.uploads.c.payload).where(self.uploads.c.sha256 == digest)
            ).first()
        return json.loads(row.payload) if row else None

    def put_job(self, value: dict[str, Any]) -> None:
        """Insert or compare-and-swap a job payload.

        ``_revision`` is intentionally stored inside the JSON payload so old
        databases do not require a schema migration.  Callers receive the new
        revision in the dict they supplied.
        """
        job_id = value["job_id"]
        with self.engine.begin() as db:
            row = db.execute(
                select(self.job_table.c.payload).where(self.job_table.c.job_id == job_id)
            ).first()
            if not row:
                payload_value = dict(value)
                payload_value["_revision"] = 1
                db.execute(
                    self.job_table.insert().values(
                        job_id=job_id,
                        payload=json.dumps(payload_value),
                    )
                )
                value["_revision"] = 1
                return

            current_payload = str(row.payload)
            current = json.loads(current_payload)
            current_revision = int(current.get("_revision", 0) or 0)
            expected_revision = int(value.get("_revision", current_revision) or 0)
            if current_revision and expected_revision != current_revision:
                raise ConcurrentUpdateError(
                    f"stale job revision for {job_id}: expected {expected_revision}, current {current_revision}"
                )
            updated = dict(value)
            updated["_revision"] = current_revision + 1
            result = db.execute(
                self.job_table.update().where(
                    (self.job_table.c.job_id == job_id)
                    & (self.job_table.c.payload == current_payload)
                ).values(payload=json.dumps(updated))
            )
            if result.rowcount != 1:
                raise ConcurrentUpdateError(f"job changed concurrently: {job_id}")
            value["_revision"] = updated["_revision"]

    def transition_job(
        self,
        job_id: str,
        *,
        expected_statuses: Iterable[str] | None = None,
        updates: dict[str, Any],
    ) -> dict[str, Any]:
        """Atomically transition a job only when its current status is allowed."""
        allowed = set(expected_statuses or [])
        with self.engine.begin() as db:
            row = db.execute(
                select(self.job_table.c.payload).where(self.job_table.c.job_id == job_id)
            ).first()
            if not row:
                raise KeyError(job_id)
            current_payload = str(row.payload)
            current = json.loads(current_payload)
            if allowed and str(current.get("status")) not in allowed:
                raise ConcurrentUpdateError(
                    f"job {job_id} status {current.get('status')!r} cannot make this transition"
                )
            updated = dict(current)
            updated.update(updates)
            updated["_revision"] = int(current.get("_revision", 0) or 0) + 1
            result = db.execute(
                self.job_table.update().where(
                    (self.job_table.c.job_id == job_id)
                    & (self.job_table.c.payload == current_payload)
                ).values(payload=json.dumps(updated))
            )
            if result.rowcount != 1:
                raise ConcurrentUpdateError(f"job changed concurrently: {job_id}")
            return updated

    def job(self, job_id: str) -> dict[str, Any] | None:
        with self.engine.connect() as db:
            row = db.execute(
                select(self.job_table.c.payload).where(self.job_table.c.job_id == job_id)
            ).first()
        return json.loads(row.payload) if row else None

    def jobs(self) -> list[dict[str, Any]]:
        with self.engine.connect() as db:
            rows = db.execute(select(self.job_table.c.payload)).all()
        return [json.loads(row.payload) for row in reversed(rows)]
