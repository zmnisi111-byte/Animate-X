from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Any

from .env import require_env


@dataclass(frozen=True)
class RunPodServerlessConfig:
    api_key: str
    endpoint_id: str
    api_base: str = "https://api.runpod.ai/v2"

    @classmethod
    def from_env(cls) -> "RunPodServerlessConfig":
        return cls(
            api_key=require_env("RUNPOD_API_KEY"),
            endpoint_id=require_env("RUNPOD_ENDPOINT_ID"),
            api_base=os.getenv("RUNPOD_API_BASE", "https://api.runpod.ai/v2").rstrip("/"),
        )


class RunPodServerlessClient:
    def __init__(self, config: RunPodServerlessConfig):
        self.config = config

    def submit(self, *, batch_id: str, manifest_url: str) -> dict[str, Any]:
        return self._request(
            "POST",
            f"/{self.config.endpoint_id}/run",
            {"input": {"batch_id": batch_id, "manifest_url": manifest_url}},
        )

    def status(self, job_id: str) -> dict[str, Any]:
        return self._request("GET", f"/{self.config.endpoint_id}/status/{job_id}", None)

    def _request(self, method: str, path: str, payload: dict[str, Any] | None) -> dict[str, Any]:
        data = json.dumps(payload).encode("utf-8") if payload is not None else None
        request = urllib.request.Request(
            f"{self.config.api_base}{path}",
            data=data,
            method=method,
            headers={
                "Authorization": f"Bearer {self.config.api_key}",
                "Content-Type": "application/json",
                "User-Agent": "Mozilla/5.0 Animate-X/0.1",
            },
        )
        try:
            with urllib.request.urlopen(request, timeout=60) as response:
                return json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            body = exc.read().decode("utf-8", errors="replace")
            raise RuntimeError(f"RunPod API {exc.code}: {body}") from exc
