"""Canonical ASR model policy for every pipeline entry point.

Production jobs use only project-controlled ASR artifacts.  A profile may tune
inference behaviour elsewhere, but it must never silently select a model that
the project provisioner cannot supply.
"""

from __future__ import annotations

from pathlib import Path

PROJECT_ASR_MODEL = "large-v3-turbo"
DEFAULT_PROFILE = "balanced"
SUPPORTED_PROFILES = ("fast", "balanced", "accurate")

# Until additional integrity-pinned artifacts are added to models/asr/, every
# production profile uses the single project-controlled model.  This is
# intentionally explicit: profile names must not imply an unavailable model.
PROFILE_MODELS = {
    "fast": PROJECT_ASR_MODEL,
    "balanced": PROJECT_ASR_MODEL,
    "accurate": PROJECT_ASR_MODEL,
}


def normalize_profile(profile: str) -> str:
    value = str(profile or DEFAULT_PROFILE).strip().casefold()
    if value not in PROFILE_MODELS:
        allowed = ", ".join(SUPPORTED_PROFILES)
        raise ValueError(f"unknown transcription profile: {profile!r}; expected one of: {allowed}")
    return value


def resolve_transcription_model(
    profile: str,
    explicit_model: str = "",
    *,
    allow_local_path: bool = True,
) -> str:
    """Resolve and validate the ASR model for a profile.

    Named production models are restricted to ``PROJECT_ASR_MODEL`` because it
    is the only model currently backed by an integrity-pinned project artifact.
    A local directory can still be used explicitly by local/development paths;
    remote API requests disable that escape hatch.
    """

    normalized_profile = normalize_profile(profile)
    model = str(explicit_model or "").strip()
    if not model:
        return PROFILE_MODELS[normalized_profile]
    if model == PROJECT_ASR_MODEL:
        return PROJECT_ASR_MODEL
    if allow_local_path:
        candidate = Path(model).expanduser()
        if candidate.is_dir():
            return str(candidate.resolve())
    raise ValueError(
        f"unsupported ASR model: {model!r}; production model is {PROJECT_ASR_MODEL!r}"
    )
