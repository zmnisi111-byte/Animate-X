from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Profile:
    name: str
    generation_size: str
    final_size: str
    purpose: str
    mock_speed_multiplier: float


PROFILES: dict[str, Profile] = {
    "Draft": Profile("Draft", "480x854", "720x1280", "Testing", 0.35),
    "TikTok Standard": Profile("TikTok Standard", "720x1280", "1080x1920", "Normal production", 0.7),
    "TikTok Quality": Profile("TikTok Quality", "720x1280", "1080x1920", "Important clips", 1.0),
}


def profile_names() -> list[str]:
    return list(PROFILES)


def get_profile(name: str) -> Profile:
    try:
        return PROFILES[name]
    except KeyError as exc:
        raise ValueError(f"Unknown profile '{name}'. Choose one of: {', '.join(profile_names())}") from exc

