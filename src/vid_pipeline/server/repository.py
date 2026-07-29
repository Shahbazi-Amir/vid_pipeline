"""Persistent upload and job repository for SQLite or PostgreSQL."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import Column, MetaData, String, Table, Text, create_engine, select
from sqlalchemy.engine import Engine


def now() -> str:
    return datetime.now(UTC).isoformat()


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
        with self.engine.begin() as db:
            existing = db.execute(
                select(self.job_table.c.job_id).where(self.job_table.c.job_id == value["job_id"])
            ).first()
            payload = json.dumps(value)
            if existing:
                db.execute(
                    self.job_table.update().where(
                        self.job_table.c.job_id == value["job_id"]
                    ).values(payload=payload)
                )
            else:
                db.execute(self.job_table.insert().values(job_id=value["job_id"], payload=payload))

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
