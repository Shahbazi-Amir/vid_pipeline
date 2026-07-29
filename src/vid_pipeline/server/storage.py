"""Object storage backends for uploaded inputs and result artifacts."""

from __future__ import annotations

import shutil
from pathlib import Path
from typing import BinaryIO, Protocol


class ObjectStore(Protocol):
    def put_file(self, source: Path, key: str) -> str: ...
    def open(self, key: str) -> BinaryIO: ...
    def path(self, key: str) -> Path: ...
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

    def list(self, prefix: str) -> list[str]:
        root = self.path(prefix)
        return [
            str(path.relative_to(self.root))
            for path in root.rglob("*")
            if path.is_file()
        ] if root.exists() else []


class S3ArtifactStore:
    def __init__(self, bucket: str, *, endpoint_url: str | None = None, **credentials: str) -> None:
        import boto3

        self.bucket = bucket
        self.client = boto3.client("s3", endpoint_url=endpoint_url, **credentials)

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
            Params={"Bucket": self.bucket, "Key": key, "UploadId": upload_id,
                    "PartNumber": part_number},
            ExpiresIn=3600,
        )

    def complete_multipart_upload(
        self, key: str, upload_id: str, parts: list[dict[str, str | int]]
    ) -> str:
        self.client.complete_multipart_upload(
            Bucket=self.bucket, Key=key, UploadId=upload_id,
            MultipartUpload={"Parts": parts},
        )
        return key

    def abort_multipart_upload(self, key: str, upload_id: str) -> None:
        self.client.abort_multipart_upload(
            Bucket=self.bucket, Key=key, UploadId=upload_id
        )

    def open(self, key: str) -> BinaryIO:
        return self.client.get_object(Bucket=self.bucket, Key=key)["Body"]

    def path(self, key: str) -> Path:
        raise NotImplementedError("S3 objects must be materialized by the worker")

    def list(self, prefix: str) -> list[str]:
        result = self.client.list_objects_v2(Bucket=self.bucket, Prefix=prefix)
        return [item["Key"] for item in result.get("Contents", [])]
