from __future__ import annotations

import subprocess
from pathlib import Path

from .media import ffmpeg_path


def create_sample_assets(root: Path) -> tuple[Path, Path]:
    root.mkdir(parents=True, exist_ok=True)
    video = root / "dance_01.mp4"
    reference = root / "ari_reference.png"
    ffmpeg = ffmpeg_path()

    if ffmpeg:
        subprocess.run(
            [
                ffmpeg,
                "-y",
                "-f",
                "lavfi",
                "-i",
                "testsrc2=size=360x640:rate=24",
                "-t",
                "2",
                "-pix_fmt",
                "yuv420p",
                str(video),
            ],
            check=True,
            capture_output=True,
            text=True,
            timeout=60,
        )
        subprocess.run(
            [
                ffmpeg,
                "-y",
                "-f",
                "lavfi",
                "-i",
                "color=c=0x6fa8dc:s=512x768",
                "-frames:v",
                "1",
                str(reference),
            ],
            check=True,
            capture_output=True,
            text=True,
            timeout=60,
        )
    else:
        video.write_bytes(b"placeholder video")
        reference.write_bytes(b"placeholder image")

    return video, reference

