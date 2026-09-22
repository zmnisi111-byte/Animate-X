from __future__ import annotations

import json
import time
from pathlib import Path

from .. import states
from ..config import AppConfig
from ..db import JobStore
from ..media import copy_or_transcode_video, extract_first_frame
from ..planning import GENERATED_ANCHOR
from ..profiles import get_profile
from ..storage import LocalDriveStore, LocalTempStore


class MockWanWorker:
    """Exercises production state transitions without requiring a GPU."""

    def __init__(self, config: AppConfig, store: JobStore):
        self.config = config
        self.store = store
        self.temp = LocalTempStore(config.temp_dir)
        self.drive = LocalDriveStore(config.drive_dir)

    def run_manifest(self, manifest_path: Path) -> dict[str, float | int]:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        batch_id = manifest["batch_id"]
        self.store.mark_batch_started(batch_id)

        total_gpu_seconds = 0.0
        completed = 0
        failed = 0

        for job in manifest["jobs"]:
            gpu_seconds = 0.0
            try:
                source = Path(job["source_path"])
                reference = Path(job["reference_path"])
                if not source.exists():
                    raise FileNotFoundError(f"Source video not found: {source}")
                if not reference.exists():
                    raise FileNotFoundError(f"Reference image not found: {reference}")

                self.store.update_job(job["id"], states.UPLOADING, "Staging inputs")
                staged_source, staged_reference = self.temp.stage_job(batch_id, job["id"], source, reference)

                self.store.update_job(
                    job["id"],
                    states.READY,
                    "Inputs staged",
                    payload={"source": str(staged_source), "reference": str(staged_reference), "mode": job["mode"]},
                )

                if job["first_frame_strategy"] == GENERATED_ANCHOR:
                    self.store.update_job(job["id"], states.FIRST_FRAME, "Generating first-frame anchor")
                    anchor_path = self.config.temp_dir / batch_id / job["id"] / "outputs" / "first_frame_anchor.png"
                    extract_first_frame(staged_source, anchor_path)

                profile = get_profile(job["profile"])
                simulated_seconds = max(
                    0.2,
                    float(job["duration_seconds"] or 1.0)
                    * profile.mock_speed_multiplier
                    * float(job["window_count"]),
                )

                started = time.perf_counter()
                self.store.update_job(job["id"], states.GENERATING, "Mock Wan generation started")
                time.sleep(min(1.5, simulated_seconds))
                gpu_seconds += time.perf_counter() - started

                self.store.update_job(job["id"], states.UPSCALING, "Mock upscale")
                time.sleep(0.1)

                self.store.update_job(job["id"], states.ENCODING, "Encoding final MP4")
                output = self.temp.output_path(batch_id, job["id"])
                copy_or_transcode_video(staged_source, output)

                self.store.update_job(job["id"], states.UPLOADING_TO_DRIVE, "Copying to local Drive library")
                drive_path = self.drive.upload(job["character"], output)

                cost = (gpu_seconds / 3600.0) * self.config.gpu_hourly_rate_usd
                self.store.update_job(
                    job["id"],
                    states.COMPLETED,
                    "Completed",
                    output_path=output,
                    drive_path=drive_path,
                    gpu_seconds=gpu_seconds,
                    estimated_cost=cost,
                )
                total_gpu_seconds += gpu_seconds
                completed += 1
            except Exception as exc:
                failed += 1
                self.store.update_job(job["id"], states.FAILED, "Job failed", error=str(exc))

        total_cost = (total_gpu_seconds / 3600.0) * self.config.gpu_hourly_rate_usd
        self.store.mark_batch_done(batch_id, total_gpu_seconds, total_cost)
        return {"completed": completed, "failed": failed, "gpu_seconds": total_gpu_seconds, "estimated_cost": total_cost}
