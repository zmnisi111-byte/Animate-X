from __future__ import annotations

import math
import subprocess
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class ChunkWindow:
    index: int
    start_frame: int
    end_frame: int
    start_seconds: float
    duration_seconds: float
    frame_count: int


def chunk_windows(
    *,
    estimated_frames: int,
    fps: int,
    clip_len: int,
    overlap_frames: int,
) -> list[ChunkWindow]:
    if estimated_frames <= 0:
        return []
    if fps <= 0:
        raise ValueError("fps must be positive")
    if clip_len <= 0:
        raise ValueError("clip_len must be positive")
    if overlap_frames < 0:
        raise ValueError("overlap_frames must not be negative")
    if estimated_frames > clip_len and overlap_frames >= clip_len:
        raise ValueError("overlap_frames must be smaller than clip_len")

    stride = clip_len - overlap_frames
    windows: list[ChunkWindow] = []
    start = 0
    index = 0
    while start < estimated_frames:
        end = min(start + clip_len, estimated_frames)
        frame_count = end - start
        windows.append(
            ChunkWindow(
                index=index,
                start_frame=start,
                end_frame=end,
                start_seconds=start / fps,
                duration_seconds=frame_count / fps,
                frame_count=frame_count,
            )
        )
        if end >= estimated_frames:
            break
        start += stride
        index += 1
    return windows


def extract_video_chunk(source: Path, dest: Path, window: ChunkWindow, *, fps: int) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    cmd = [
        "ffmpeg",
        "-y",
        "-ss",
        f"{window.start_seconds:.6f}",
        "-t",
        f"{window.duration_seconds:.6f}",
        "-i",
        str(source),
        "-an",
        "-r",
        str(fps),
        "-c:v",
        "libx264",
        "-pix_fmt",
        "yuv420p",
        "-movflags",
        "+faststart",
        str(dest),
    ]
    _run_ffmpeg(cmd)


def trim_chunk_start(source: Path, dest: Path, *, trim_seconds: float) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    if trim_seconds <= 0:
        dest.write_bytes(source.read_bytes())
        return
    cmd = [
        "ffmpeg",
        "-y",
        "-ss",
        f"{trim_seconds:.6f}",
        "-i",
        str(source),
        "-an",
        "-c:v",
        "libx264",
        "-pix_fmt",
        "yuv420p",
        "-movflags",
        "+faststart",
        str(dest),
    ]
    _run_ffmpeg(cmd)


def concat_videos(parts: list[Path], dest: Path) -> None:
    if not parts:
        raise ValueError("No chunk videos to concatenate")
    dest.parent.mkdir(parents=True, exist_ok=True)
    list_file = dest.parent / "concat.txt"
    list_file.write_text(
        "".join(f"file '{part.resolve().as_posix()}'\n" for part in parts),
        encoding="utf-8",
    )
    cmd = [
        "ffmpeg",
        "-y",
        "-f",
        "concat",
        "-safe",
        "0",
        "-i",
        str(list_file),
        "-c",
        "copy",
        str(dest),
    ]
    try:
        _run_ffmpeg(cmd)
    except RuntimeError:
        cmd = [
            "ffmpeg",
            "-y",
            "-f",
            "concat",
            "-safe",
            "0",
            "-i",
            str(list_file),
            "-an",
            "-c:v",
            "libx264",
            "-pix_fmt",
            "yuv420p",
            "-movflags",
            "+faststart",
            str(dest),
        ]
        _run_ffmpeg(cmd)


def window_count_for_frames(*, estimated_frames: int, clip_len: int, overlap_frames: int) -> int:
    if estimated_frames <= clip_len:
        return 1
    stride = clip_len - overlap_frames
    return int(math.ceil((estimated_frames - clip_len) / stride)) + 1


def _run_ffmpeg(cmd: list[str]) -> None:
    result = subprocess.run(cmd, text=True, capture_output=True)
    if result.returncode != 0:
        raise RuntimeError(
            "ffmpeg failed with exit code "
            f"{result.returncode}: {' '.join(cmd)}\nSTDOUT:\n{result.stdout[-2000:]}\nSTDERR:\n{result.stderr[-4000:]}"
        )
