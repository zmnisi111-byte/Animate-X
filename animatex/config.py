from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class AppConfig:
    root: Path
    data_dir: Path
    db_path: Path
    temp_dir: Path
    manifests_dir: Path
    drive_dir: Path
    gpu_hourly_rate_usd: float = 2.09

    @classmethod
    def from_root(cls, root: Path | None = None) -> "AppConfig":
        base = (root or Path.cwd()).resolve()
        data = base / "data"
        return cls(
            root=base,
            data_dir=data,
            db_path=data / "animatex.sqlite",
            temp_dir=data / "temp",
            manifests_dir=data / "manifests",
            drive_dir=data / "drive",
        )

    def ensure_dirs(self) -> None:
        for path in (self.data_dir, self.temp_dir, self.manifests_dir, self.drive_dir):
            path.mkdir(parents=True, exist_ok=True)

