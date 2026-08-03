"""Canonical ASR model policy for pipeline profiles."""

from __future__ import annotations

PROFILE_MODELS = {
    "fast": "small",
    "balanced": "large-v3-turbo",
    "accurate": "large-v3",
}

DEFAULT_PROFILE = "balanced"


def resolve_transcription_model(profile: str, explicit_model: str = "") -> str:
    """Return an explicit model or the canonical model for *profile*."""
    model = explicit_model.strip()
    if model:
        return model
    try:
        return PROFILE_MODELS[profile]
    except KeyError as exc:
        raise ValueError(f"unknown transcription profile: {profile}") from exc
