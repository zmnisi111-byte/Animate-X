from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path

from .config import AppConfig
from .db import JobStore
from .profiles import get_profile


@dataclass(frozen=True)
class ManifestJob:
    id: str
    character: str
    mode: str
    source_path: str
    reference_path: str
    source_hash: str
    reference_hash: str
    profile: str
    generation_size: str
    final_size: str
    duration_seconds: float
    processing_mode: str
    target_fps: int
    estimated_frames: int
    window_count: int
    overlap_frames: int
    first_frame_strategy: str
    group_key: str


def duration_bucket(seconds: float) -> str:
    if seconds <= 0:
        return "unknown"
    return f"{round(seconds / 5) * 5:03d}s"


def build_manifest(config: AppConfig, store: JobStore) -> tuple[str | None, Path | None, list[ManifestJob]]:
    jobs = store.queued_jobs()
    if not jobs:
        return None, None, []

    manifest_jobs: list[ManifestJob] = []
    for row in jobs:
        profile = get_profile(row["profile"])
        group_key = "|".join(
            [
                row["character"].strip().lower(),
                row["mode"],
                row["reference_hash"][:16],
                row["profile"],
                profile.generation_size,
                row["processing_mode"],
                str(row["window_count"]),
                duration_bucket(float(row["duration_seconds"])),
            ]
        )
        manifest_jobs.append(
            ManifestJob(
                id=row["id"],
                character=row["character"],
                mode=row["mode"],
                source_path=row["source_path"],
                reference_path=row["reference_path"],
                source_hash=row["source_hash"],
                reference_hash=row["reference_hash"],
                profile=row["profile"],
                generation_size=profile.generation_size,
                final_size=profile.final_size,
                duration_seconds=float(row["duration_seconds"]),
                processing_mode=row["processing_mode"],
                target_fps=int(row["target_fps"]),
                estimated_frames=int(row["estimated_frames"]),
                window_count=int(row["window_count"]),
                overlap_frames=int(row["overlap_frames"]),
                first_frame_strategy=row["first_frame_strategy"],
                group_key=group_key,
            )
        )

    config.manifests_dir.mkdir(parents=True, exist_ok=True)
    placeholder = config.manifests_dir / "pending.json"
    batch_id = store.create_batch([job.id for job in manifest_jobs], placeholder)
    manifest_path = config.manifests_dir / f"{batch_id}.json"
    payload = {
        "batch_id": batch_id,
        "jobs": [asdict(job) for job in sorted(manifest_jobs, key=lambda j: (j.group_key, j.id))],
        "groups": sorted({job.group_key for job in manifest_jobs}),
    }
    manifest_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    with store.connect() as conn:
        conn.execute("UPDATE batches SET manifest_path = ? WHERE id = ?", (str(manifest_path), batch_id))

    return batch_id, manifest_path, manifest_jobs
