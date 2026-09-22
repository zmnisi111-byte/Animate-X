from __future__ import annotations

import os
import json
from dataclasses import dataclass
from pathlib import Path

from .env import require_env


@dataclass(frozen=True)
class R2Settings:
    endpoint_url: str
    access_key_id: str
    secret_access_key: str
    bucket: str

    @classmethod
    def from_env(cls) -> "R2Settings":
        return cls(
            endpoint_url=require_env("R2_ENDPOINT_URL"),
            access_key_id=require_env("R2_ACCESS_KEY_ID"),
            secret_access_key=require_env("R2_SECRET_ACCESS_KEY"),
            bucket=require_env("R2_BUCKET"),
        )


class R2Uploader:
    def __init__(self, settings: R2Settings):
        import boto3

        self.settings = settings
        self.client = boto3.client(
            "s3",
            endpoint_url=settings.endpoint_url,
            aws_access_key_id=settings.access_key_id,
            aws_secret_access_key=settings.secret_access_key,
            region_name="auto",
        )

    def upload_file(self, path: Path, key: str, content_type: str | None = None) -> str:
        extra_args = {"ContentType": content_type} if content_type else None
        if extra_args:
            self.client.upload_file(str(path), self.settings.bucket, key, ExtraArgs=extra_args)
        else:
            self.client.upload_file(str(path), self.settings.bucket, key)
        return f"r2://{self.settings.bucket}/{key}"

    def upload_json(self, payload: object, key: str) -> str:
        data = json.dumps(payload, indent=2).encode("utf-8")
        self.client.put_object(
            Bucket=self.settings.bucket,
            Key=key,
            Body=data,
            ContentType="application/json",
        )
        return f"r2://{self.settings.bucket}/{key}"
