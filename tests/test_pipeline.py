from __future__ import annotations

from pathlib import Path

from animatex.chunking import chunk_windows
from animatex.cli import main


def test_longform_chunk_windows_match_planner_shape() -> None:
    windows = chunk_windows(estimated_frames=784, fps=30, clip_len=77, overlap_frames=5)

    assert len(windows) == 11
    assert windows[0].start_frame == 0
    assert windows[1].start_frame == 72
    assert windows[-1].end_frame == 784
    assert windows[-1].frame_count == 64


def test_pipeline_end_to_end(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    assert main(["init"]) == 0
    assert main(["sample"]) == 0
    assert main(
        [
            "add",
            "--video",
            "samples/dance_01.mp4",
            "--reference",
            "samples/ari_reference.png",
            "--character",
            "Ari",
            "--mode",
            "character_swap",
            "--profile",
            "Draft",
        ]
    ) == 0
    assert main(["run"]) == 0
    assert main(["queue"]) == 0

    outputs = list((tmp_path / "data" / "drive").rglob("*.mp4"))
    assert len(outputs) == 1
    assert outputs[0].stat().st_size > 0
