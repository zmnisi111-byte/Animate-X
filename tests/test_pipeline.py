from __future__ import annotations

from pathlib import Path

from animatex.cli import main


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
