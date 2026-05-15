"""Small MinIO client wrapper used by upload and future object storage flows."""

from __future__ import annotations

from io import BytesIO

from minio import Minio

from app.config import get_settings


class MinioStorageClient:
    """Thin wrapper around the MinIO SDK."""

    def __init__(self) -> None:
        settings = get_settings().minio
        self._client = Minio(
            settings.endpoint,
            access_key=settings.access_key,
            secret_key=settings.secret_key,
            secure=settings.secure,
        )

    def ensure_bucket(self, bucket_name: str) -> None:
        """Create the bucket when it does not already exist."""
        if not self._client.bucket_exists(bucket_name):
            self._client.make_bucket(bucket_name)

    def put_bytes(
        self,
        bucket_name: str,
        object_name: str,
        content: bytes,
        content_type: str,
    ) -> None:
        """Upload bytes to object storage."""
        self._client.put_object(
            bucket_name=bucket_name,
            object_name=object_name,
            data=BytesIO(content),
            length=len(content),
            content_type=content_type,
        )


def get_minio_client() -> MinioStorageClient:
    """Return a new MinIO wrapper instance."""
    return MinioStorageClient()
