from __future__ import annotations

import shutil
from datetime import datetime
from pathlib import Path


class LocalTempStore:
    def __init__(self, root: Path):
        self.root = root

    def stage_job(self, batch_id: str, job_id: str, source: Path, reference: Path) -> tuple[Path, Path]:
        job_dir = self.root / batch_id / job_id / "inputs"
        job_dir.mkdir(parents=True, exist_ok=True)
        source_dest = job_dir / source.name
        reference_dest = job_dir / reference.name
        shutil.copy2(source, source_dest)
        shutil.copy2(reference, reference_dest)
        return source_dest, reference_dest

    def output_path(self, batch_id: str, job_id: str, extension: str = ".mp4") -> Path:
        return self.root / batch_id / job_id / "outputs" / f"{job_id}{extension}"


class LocalDriveStore:
    def __init__(self, root: Path):
        self.root = root

    def upload(self, character: str, source_output: Path) -> Path:
        date_folder = datetime.now().strftime("%Y-%m-%d")
        dest_dir = self.root / "AI Influencer" / character / date_folder
        dest_dir.mkdir(parents=True, exist_ok=True)
        dest = dest_dir / source_output.name
        shutil.copy2(source_output, dest)
        return dest

