from __future__ import annotations

import math
from dataclasses import dataclass

from .modes import CHARACTER_SWAP

TARGET_FPS = 30
WAN_CLIP_LEN = 77
SHORT_OVERLAP_FRAMES = 1
LONGFORM_OVERLAP_FRAMES = 5
SINGLE_WINDOW = "single_window"
LONGFORM_WINDOWED = "longform_windowed"
DIRECT_REFERENCE = "direct_reference"
GENERATED_ANCHOR = "generated_anchor"


@dataclass(frozen=True)
class GenerationPlan:
    processing_mode: str
    target_fps: int
    estimated_frames: int
    window_count: int
    overlap_frames: int
    first_frame_strategy: str


def plan_generation(duration_seconds: float, job_mode: str) -> GenerationPlan:
    frames = max(1, int(math.ceil(max(duration_seconds, 0.0) * TARGET_FPS)))
    processing_mode = SINGLE_WINDOW if frames <= WAN_CLIP_LEN else LONGFORM_WINDOWED
    overlap = SHORT_OVERLAP_FRAMES if processing_mode == SINGLE_WINDOW else LONGFORM_OVERLAP_FRAMES
    stride = WAN_CLIP_LEN - overlap
    window_count = 1 if frames <= WAN_CLIP_LEN else int(math.ceil((frames - WAN_CLIP_LEN) / stride)) + 1
    first_frame_strategy = DIRECT_REFERENCE
    if processing_mode == LONGFORM_WINDOWED or job_mode == CHARACTER_SWAP:
        first_frame_strategy = GENERATED_ANCHOR
    return GenerationPlan(
        processing_mode=processing_mode,
        target_fps=TARGET_FPS,
        estimated_frames=frames,
        window_count=window_count,
        overlap_frames=overlap,
        first_frame_strategy=first_frame_strategy,
    )


def processing_label(mode: str) -> str:
    if mode == LONGFORM_WINDOWED:
        return "Longform Windowed"
    return "Single Window"


def first_frame_label(strategy: str) -> str:
    if strategy == GENERATED_ANCHOR:
        return "Generated Anchor"
    return "Direct Reference"

