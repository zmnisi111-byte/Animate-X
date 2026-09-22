from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlparse

import boto3


@dataclass(frozen=True)
class R2Config:
    endpoint_url: str
    access_key_id: str
    secret_access_key: str
    bucket: str
    public_base_url: str | None = None

    @classmethod
    def from_env(cls) -> "R2Config":
        return cls(
            endpoint_url=require_env("R2_ENDPOINT_URL"),
            access_key_id=require_env("R2_ACCESS_KEY_ID"),
            secret_access_key=require_env("R2_SECRET_ACCESS_KEY"),
            bucket=require_env("R2_BUCKET"),
            public_base_url=os.getenv("R2_PUBLIC_BASE_URL"),
        )


class R2Store:
    def __init__(self, config: R2Config):
        self.config = config
        self.client = boto3.client(
            "s3",
            endpoint_url=config.endpoint_url,
            aws_access_key_id=config.access_key_id,
            aws_secret_access_key=config.secret_access_key,
            region_name="auto",
        )

    def download(self, uri: str, dest: Path) -> Path:
        dest.parent.mkdir(parents=True, exist_ok=True)
        bucket, key = self._parse_uri(uri)
        self.client.download_file(bucket, key, str(dest))
        return dest

    def upload(self, source: Path, key: str, content_type: str | None = None) -> str:
        extra_args = {"ContentType": content_type} if content_type else None
        if extra_args:
            self.client.upload_file(str(source), self.config.bucket, key, ExtraArgs=extra_args)
        else:
            self.client.upload_file(str(source), self.config.bucket, key)
        return self.uri_for_key(key)

    def uri_for_key(self, key: str) -> str:
        if self.config.public_base_url:
            return f"{self.config.public_base_url.rstrip('/')}/{key}"
        return f"r2://{self.config.bucket}/{key}"

    def _parse_uri(self, uri: str) -> tuple[str, str]:
        if uri.startswith("r2://"):
            parsed = urlparse(uri)
            return parsed.netloc, parsed.path.lstrip("/")
        if uri.startswith("s3://"):
            parsed = urlparse(uri)
            return parsed.netloc, parsed.path.lstrip("/")
        if self.config.public_base_url and uri.startswith(self.config.public_base_url.rstrip("/") + "/"):
            return self.config.bucket, uri[len(self.config.public_base_url.rstrip("/") + "/") :]
        raise ValueError(f"Unsupported R2 URI: {uri}")


def require_env(name: str) -> str:
    value = os.getenv(name)
    if not value:
        raise RuntimeError(f"Missing required environment variable: {name}")
    return value

