import io
import os
from datetime import datetime, timezone
from typing import BinaryIO

import boto3
from botocore.client import Config
from botocore.exceptions import ClientError

from app.core.config import settings
from app.core.exceptions import AppException


class StorageService:
    def __init__(self):
        self.bucket = settings.s3_bucket
        self.client = boto3.client(
            "s3",
            endpoint_url=settings.s3_endpoint,
            aws_access_key_id=settings.s3_access_key,
            aws_secret_access_key=settings.s3_secret_key,
            config=Config(signature_version="s3v4"),
            region_name="us-east-1",
        )
        self.local_root = os.path.join(os.getcwd(), "storage")

    def ensure_bucket(self) -> None:
        try:
            self.client.head_bucket(Bucket=self.bucket)
        except ClientError:
            self.client.create_bucket(Bucket=self.bucket)

    def upload(
        self,
        key: str,
        file_obj: BinaryIO,
        content_type: str,
        size: int | None = None,
    ) -> str:
        try:
            self.client.upload_fileobj(
                file_obj,
                self.bucket,
                key,
                ExtraArgs={"ContentType": content_type},
            )
            return key
        except ClientError as exc:
            self._local_write(key, file_obj, content_type)
            return key

    def download(self, key: str) -> bytes:
        try:
            buf = io.BytesIO()
            self.client.download_fileobj(self.bucket, key, buf)
            return buf.getvalue()
        except ClientError:
            return self._local_read(key)

    def delete(self, key: str) -> None:
        try:
            self.client.delete_object(Bucket=self.bucket, Key=key)
        except ClientError:
            pass
        local = self._local_path(key)
        if os.path.exists(local):
            os.remove(local)

    def public_url(self, key: str) -> str:
        if settings.s3_public_base_url:
            return f"{settings.s3_public_base_url.rstrip('/')}/{key}"
        return f"{settings.s3_endpoint.rstrip('/')}/{self.bucket}/{key}"

    # ---------- local fallback ----------
    def _local_path(self, key: str) -> str:
        return os.path.join(self.local_root, key.replace("/", os.sep))

    def _local_write(self, key: str, file_obj: BinaryIO, _content_type: str) -> None:
        path = self._local_path(key)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        file_obj.seek(0)
        with open(path, "wb") as fh:
            fh.write(file_obj.read())

    def _local_read(self, key: str) -> bytes:
        path = self._local_path(key)
        if not os.path.exists(path):
            raise AppException("File not found in storage", status_code=404, code="object_not_found")
        with open(path, "rb") as fh:
            return fh.read()

    @staticmethod
    def build_key(scope: str, user_id: int, original_filename: str) -> str:
        stamp = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S%f")
        safe_name = os.path.basename(original_filename).replace(" ", "_")
        return f"{scope}/user_{user_id}/{stamp}_{safe_name}"


storage = StorageService()