from __future__ import annotations

import shutil
import subprocess
from pathlib import Path


def ffmpeg_path() -> str | None:
    return shutil.which("ffmpeg")


def copy_or_transcode_video(source: Path, dest: Path) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    ffmpeg = ffmpeg_path()
    if not ffmpeg:
        shutil.copy2(source, dest)
        return
    try:
        subprocess.run(
            [
                ffmpeg,
                "-y",
                "-i",
                str(source),
                "-c:v",
                "libx264",
                "-pix_fmt",
                "yuv420p",
                "-c:a",
                "aac",
                "-movflags",
                "+faststart",
                str(dest),
            ],
            check=True,
            capture_output=True,
            text=True,
            timeout=900,
        )
    except Exception:
        shutil.copy2(source, dest)

