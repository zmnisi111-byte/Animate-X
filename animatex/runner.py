from __future__ import annotations

from .batch import build_manifest
from .config import AppConfig
from .db import JobStore
from .workers import MockWanWorker


def run_due_batch(config: AppConfig, store: JobStore) -> dict[str, float | int | str]:
    batch_id, manifest_path, jobs = build_manifest(config, store)
    if not batch_id or not manifest_path:
        return {"batch_id": "", "completed": 0, "failed": 0, "gpu_seconds": 0.0, "estimated_cost": 0.0}
    result = MockWanWorker(config, store).run_manifest(manifest_path)
    return {"batch_id": batch_id, **result}

