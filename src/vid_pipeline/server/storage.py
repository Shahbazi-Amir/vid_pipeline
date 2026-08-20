"""Object storage backends for uploaded inputs and result artifacts."""

from __future__ import annotations

import os
import shutil
from pathlib import Path
from typing import BinaryIO, Protocol


class ObjectStore(Protocol):
    def put_file(self, source: Path, key: str) -> str: ...
    def open(self, key: str) -> BinaryIO: ...
    def materialize(self, key: str, destination: Path) -> Path: ...
    def size(self, key: str) -> int: ...
    def list(self, prefix: str) -> list[str]: ...


class LocalArtifactStore:
    def __init__(self, root: Path) -> None:
        self.root = root.resolve()
        self.root.mkdir(parents=True, exist_ok=True)

    def path(self, key: str) -> Path:
        target = (self.root / key).resolve()
        if target != self.root and self.root not in target.parents:
            raise ValueError("unsafe storage key")
        return target

    def put_file(self, source: Path, key: str) -> str:
        target = self.path(key)
        target.parent.mkdir(parents=True, exist_ok=True)
        if source.resolve() != target:
            shutil.copy2(source, target)
        return key

    def open(self, key: str) -> BinaryIO:
        return self.path(key).open("rb")

    def materialize(self, key: str, destination: Path) -> Path:
        source = self.path(key)
        if not source.is_file():
            raise FileNotFoundError(key)
        destination.parent.mkdir(parents=True, exist_ok=True)
        if source.resolve() != destination.resolve():
            shutil.copy2(source, destination)
            return destination
        return source

    def size(self, key: str) -> int:
        return self.path(key).stat().st_size

    def list(self, prefix: str) -> list[str]:
        root = self.path(prefix)
        return [
            str(path.relative_to(self.root))
            for path in root.rglob("*")
            if path.is_file()
        ] if root.exists() else []


class S3ArtifactStore:
    def __init__(
        self,
        bucket: str,
        *,
        endpoint_url: str | None = None,
        client=None,
        **credentials: str,
    ) -> None:
        if client is None:
            import boto3

            client = boto3.client("s3", endpoint_url=endpoint_url, **credentials)
        self.bucket = bucket
        self.client = client

    def put_file(self, source: Path, key: str) -> str:
        self.client.upload_file(str(source), self.bucket, key)
        return key

    def create_multipart_upload(self, key: str, content_type: str) -> dict:
        return self.client.create_multipart_upload(
            Bucket=self.bucket, Key=key, ContentType=content_type
        )

    def presign_part(self, key: str, upload_id: str, part_number: int) -> str:
        return self.client.generate_presigned_url(
            "upload_part",
            Params={
                "Bucket": self.bucket,
                "Key": key,
                "UploadId": upload_id,
                "PartNumber": part_number,
            },
            ExpiresIn=3600,
        )

    def complete_multipart_upload(
        self, key: str, upload_id: str, parts: list[dict[str, str | int]]
    ) -> str:
        self.client.complete_multipart_upload(
            Bucket=self.bucket,
            Key=key,
            UploadId=upload_id,
            MultipartUpload={"Parts": parts},
        )
        return key

    def abort_multipart_upload(self, key: str, upload_id: str) -> None:
        self.client.abort_multipart_upload(Bucket=self.bucket, Key=key, UploadId=upload_id)

    def open(self, key: str) -> BinaryIO:
        return self.client.get_object(Bucket=self.bucket, Key=key)["Body"]

    def materialize(self, key: str, destination: Path) -> Path:
        destination.parent.mkdir(parents=True, exist_ok=True)
        temporary = destination.with_suffix(destination.suffix + ".part")
        temporary.unlink(missing_ok=True)
        try:
            self.client.download_file(self.bucket, key, str(temporary))
            temporary.replace(destination)
        except Exception:
            temporary.unlink(missing_ok=True)
            raise
        return destination

    def size(self, key: str) -> int:
        return int(self.client.head_object(Bucket=self.bucket, Key=key)["ContentLength"])

    def list(self, prefix: str) -> list[str]:
        keys: list[str] = []
        paginator = self.client.get_paginator("list_objects_v2")
        for page in paginator.paginate(Bucket=self.bucket, Prefix=prefix):
            keys.extend(str(item["Key"]) for item in page.get("Contents", []))
        return keys


def object_store_from_env(local_root: Path) -> ObjectStore:
    backend = os.getenv("VID_PIPELINE_STORAGE_BACKEND", "local").strip().lower()
    if backend == "local":
        return LocalArtifactStore(local_root)
    if backend != "s3":
        raise ValueError("VID_PIPELINE_STORAGE_BACKEND must be local or s3")
    bucket = os.getenv("VID_PIPELINE_S3_BUCKET", "").strip()
    if not bucket:
        raise ValueError("VID_PIPELINE_S3_BUCKET is required for s3 storage")
    kwargs: dict[str, str] = {}
    access_key = os.getenv("VID_PIPELINE_S3_ACCESS_KEY", "").strip()
    secret_key = os.getenv("VID_PIPELINE_S3_SECRET_KEY", "").strip()
    if access_key:
        kwargs["aws_access_key_id"] = access_key
    if secret_key:
        kwargs["aws_secret_access_key"] = secret_key
    return S3ArtifactStore(
        bucket,
        endpoint_url=os.getenv("VID_PIPELINE_S3_ENDPOINT", "").strip() or None,
        **kwargs,
    )
