from __future__ import annotations

import hashlib
import json
import shutil
import subprocess
from pathlib import Path


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def ffmpeg_path() -> str | None:
    return shutil.which("ffmpeg")


def ffprobe_path() -> str | None:
    return shutil.which("ffprobe")


def duration_seconds(path: Path) -> float:
    probe = ffprobe_path()
    if not probe:
        return 0.0
    try:
        result = subprocess.run(
            [
                probe,
                "-v",
                "error",
                "-show_entries",
                "format=duration",
                "-of",
                "json",
                str(path),
            ],
            check=True,
            capture_output=True,
            text=True,
            timeout=20,
        )
        data = json.loads(result.stdout)
        return float(data["format"]["duration"])
    except Exception:
        return 0.0


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
            timeout=120,
        )
    except Exception:
        shutil.copy2(source, dest)


def extract_first_frame(source: Path, dest: Path) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    ffmpeg = ffmpeg_path()
    if not ffmpeg:
        dest.write_bytes(b"placeholder first frame")
        return
    subprocess.run(
        [
            ffmpeg,
            "-y",
            "-i",
            str(source),
            "-frames:v",
            "1",
            str(dest),
        ],
        check=True,
        capture_output=True,
        text=True,
        timeout=60,
    )
