from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class JobMode:
    key: str
    label: str
    description: str


POSE_RETARGET = "pose_retarget"
CHARACTER_SWAP = "character_swap"

MODES: dict[str, JobMode] = {
    POSE_RETARGET: JobMode(
        POSE_RETARGET,
        "Pose Retarget",
        "Animate the reference character from pose and face motion.",
    ),
    CHARACTER_SWAP: JobMode(
        CHARACTER_SWAP,
        "Character Swap",
        "Replace the source performer with the reference character.",
    ),
}


def mode_keys() -> list[str]:
    return list(MODES)


def mode_label(key: str) -> str:
    return MODES.get(key, MODES[POSE_RETARGET]).label


def get_mode(key: str) -> JobMode:
    try:
        return MODES[key]
    except KeyError as exc:
        raise ValueError(f"Unknown job mode '{key}'. Choose one of: {', '.join(mode_keys())}") from exc

