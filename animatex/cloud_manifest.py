from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path

from .batch import build_manifest
from .config import AppConfig
from .db import JobStore
from .r2 import R2Settings, R2Uploader


def build_worker_manifest(config: AppConfig, store: JobStore) -> tuple[str | None, Path | None]:
    batch_id, manifest_path, jobs = build_manifest(config, store)
    if not batch_id or not manifest_path:
        return None, None

    payload = {
        "batch_id": batch_id,
        "jobs": [
            {
                **asdict(job),
                "source_name": Path(job.source_path).name,
                "reference_name": Path(job.reference_path).name,
                "source_uri": f"r2://{config_placeholder_bucket()}/inputs/{batch_id}/{job.id}/{Path(job.source_path).name}",
                "reference_uri": f"r2://{config_placeholder_bucket()}/inputs/{batch_id}/{job.id}/{Path(job.reference_path).name}",
            }
            for job in sorted(jobs, key=lambda item: (item.group_key, item.id))
        ],
    }
    manifest_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return batch_id, manifest_path


def config_placeholder_bucket() -> str:
    return "__R2_BUCKET__"


def stage_batch_to_r2(config: AppConfig, store: JobStore) -> tuple[str | None, str | None, Path | None]:
    settings = R2Settings.from_env()
    batch_id, manifest_path, jobs = build_manifest(config, store)
    if not batch_id or not manifest_path:
        return None, None, None

    uploader = R2Uploader(settings)
    manifest_jobs = []

    for job in sorted(jobs, key=lambda item: (item.group_key, item.id)):
        source = Path(job.source_path)
        reference = Path(job.reference_path)
        source_key = f"inputs/{batch_id}/{job.id}/{source.name}"
        reference_key = f"inputs/{batch_id}/{job.id}/{reference.name}"
        source_uri = uploader.upload_file(source, source_key)
        reference_uri = uploader.upload_file(reference, reference_key)
        manifest_jobs.append(
            {
                **asdict(job),
                "source_name": source.name,
                "reference_name": reference.name,
                "source_uri": source_uri,
                "reference_uri": reference_uri,
            }
        )

    payload = {"batch_id": batch_id, "jobs": manifest_jobs}
    manifest_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    manifest_uri = uploader.upload_json(payload, f"manifests/{batch_id}.json")
    store.mark_batch_staged(batch_id, manifest_uri)
    return batch_id, manifest_uri, manifest_path
