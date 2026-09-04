"""MinIO 对象存储客户端封装。"""

import io
from pathlib import Path

from minio import Minio
from minio.error import S3Error

from app.core.config import settings
from app.core.logging import get_logger

log = get_logger("storage")


class Storage:
    def __init__(self) -> None:
        self.client = Minio(
            settings.minio_endpoint,
            access_key=settings.minio_access_key,
            secret_key=settings.minio_secret_key,
            secure=settings.minio_secure,
        )
        self.bucket = settings.minio_bucket

    def ensure_bucket(self) -> None:
        try:
            if not self.client.bucket_exists(self.bucket):
                self.client.make_bucket(self.bucket)
        except S3Error as e:
            log.warning("MinIO 不可用，降级为本地文件存储: %s", e)

    def put_bytes(
        self, key: str, data: bytes, content_type: str = "application/octet-stream"
    ) -> str:
        try:
            self.client.put_object(
                self.bucket,
                key,
                io.BytesIO(data),
                length=len(data),
                content_type=content_type,
            )
        except S3Error as e:
            log.warning("MinIO put 失败，写入本地: %s", e)
            self._put_local(key, data)
        return key

    def put_file(
        self, key: str, path: Path, content_type: str = "application/octet-stream"
    ) -> str:
        with open(path, "rb") as f:
            return self.put_bytes(key, f.read(), content_type)

    def get_bytes(self, key: str) -> bytes | None:
        try:
            resp = self.client.get_object(self.bucket, key)
            try:
                return resp.read()
            finally:
                resp.close()
                resp.release_conn()
        except S3Error:
            return self._get_local(key)

    def exists(self, key: str) -> bool:
        try:
            return self.client.stat_object(self.bucket, key) is not None
        except S3Error:
            return self._local_path(key).exists()

    def list_objects(self, prefix: str) -> list[str]:
        try:
            return [
                o.object_name
                for o in self.client.list_objects(self.bucket, prefix=prefix)
            ]
        except S3Error:
            p = self._local_path(prefix)
            if p.is_dir():
                return [str(x) for x in p.rglob("*") if x.is_file()]
            return []

    # ---- 本地降级存储 ----
    def _local_path(self, key: str) -> Path:
        return settings.data_path / "minio" / key

    def _put_local(self, key: str, data: bytes) -> None:
        p = self._local_path(key)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(data)

    def _get_local(self, key: str) -> bytes | None:
        p = self._local_path(key)
        return p.read_bytes() if p.exists() else None


storage = Storage()
