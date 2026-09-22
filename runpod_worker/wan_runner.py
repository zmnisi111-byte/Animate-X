from __future__ import annotations

import os
import time
from dataclasses import dataclass
from pathlib import Path

from media import copy_or_transcode_video


@dataclass(frozen=True)
class WanJob:
    id: str
    source_path: Path
    reference_path: Path
    mode: str
    profile: str
    processing_mode: str
    window_count: int


class WanRunner:
    def run(self, job: WanJob, output_path: Path) -> dict[str, float | str]:
        if os.getenv("WAN_MOCK", "1") == "1":
            return self._run_mock(job, output_path)
        return self._run_real(job, output_path)

    def _run_mock(self, job: WanJob, output_path: Path) -> dict[str, float | str]:
        started = time.perf_counter()
        copy_or_transcode_video(job.source_path, output_path)
        return {
            "engine": "mock",
            "gpu_seconds": time.perf_counter() - started,
            "note": "Smoke-test worker copied/transcoded the source video.",
        }

    def _run_real(self, job: WanJob, output_path: Path) -> dict[str, float | str]:
        raise NotImplementedError(
            "WAN_MOCK=0 selected, but the official Wan2.2 Animate runtime is not wired yet."
        )

