"""MinIO object-storage wrapper for image binaries.

The MinIO SDK is synchronous; async callers (FastAPI) should wrap calls with
``asyncio.to_thread``. The Celery worker calls these methods directly.
"""
from __future__ import annotations

import io
from functools import lru_cache

from minio import Minio
from minio.error import S3Error

from ..core.config import settings


class StorageService:
    def __init__(
        self,
        endpoint: str | None = None,
        access_key: str | None = None,
        secret_key: str | None = None,
        bucket: str | None = None,
        secure: bool | None = None,
    ) -> None:
        self.bucket = bucket or settings.minio_bucket
        self.client = Minio(
            endpoint or settings.minio_endpoint,
            access_key=access_key or settings.minio_access_key,
            secret_key=secret_key or settings.minio_secret_key,
            secure=settings.minio_secure if secure is None else secure,
        )

    def ensure_bucket(self) -> None:
        if not self.client.bucket_exists(self.bucket):
            self.client.make_bucket(self.bucket)

    def put_image(
        self,
        object_key: str,
        data: bytes,
        content_type: str = "image/png",
    ) -> int:
        self.client.put_object(
            self.bucket,
            object_key,
            io.BytesIO(data),
            length=len(data),
            content_type=content_type,
        )
        return len(data)

    def get_image(self, object_key: str) -> bytes:
        response = self.client.get_object(self.bucket, object_key)
        try:
            return response.read()
        finally:
            response.close()
            response.release_conn()

    def remove_image(self, object_key: str) -> None:
        try:
            self.client.remove_object(self.bucket, object_key)
        except S3Error:
            pass


@lru_cache
def get_storage() -> StorageService:
    return StorageService()
