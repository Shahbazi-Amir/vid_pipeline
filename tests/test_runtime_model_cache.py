from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest

from vid_pipeline.asr_model import ProvisionedAsrModel
from vid_pipeline.transcribe import (
    TranscriptionConfig,
    clear_runtime_model_cache,
    transcribe_audio,
)


def test_two_transcriptions_reuse_one_whisper_model(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import vid_pipeline.transcribe as module

    clear_runtime_model_cache()
    local_model = tmp_path / "model"
    local_model.mkdir()
    audio = tmp_path / "audio.wav"
    audio.write_bytes(b"fixture")
    loads = 0

    class FakeWhisperModel:
        def __init__(self, path: str, **_kwargs):
            nonlocal loads
            loads += 1
            assert path == str(local_model)

        def transcribe(self, *_args, **_kwargs):
            return iter(()), SimpleNamespace(
                language="fa", language_probability=1.0, duration=1.0
            )

    monkeypatch.setenv("VID_PIPELINE_PERSISTENT_MODEL", "1")
    monkeypatch.setattr(
        module,
        "resolve_asr_model",
        lambda _name: ProvisionedAsrModel(
            local_model,
            {
                "name": "large-v3-turbo",
                "artifact_version": "v1",
                "asset_sha256": "a" * 64,
            },
            True,
        ),
    )
    monkeypatch.setattr(
        module,
        "_load_whisper",
        lambda: (SimpleNamespace(get_cuda_device_count=lambda: 0), FakeWhisperModel),
    )

    first = transcribe_audio(
        audio, tmp_path / "one.json", tmp_path / "one.md",
        TranscriptionConfig(device="cpu", compute_type="int8"),
    )
    second = transcribe_audio(
        audio, tmp_path / "two.json", tmp_path / "two.md",
        TranscriptionConfig(device="cpu", compute_type="int8"),
    )

    assert loads == 1
    assert first["timing"]["asr_runtime_model_cache_hit"] is False
    assert second["timing"]["asr_runtime_model_cache_hit"] is True


def test_persistent_model_can_be_disabled(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import vid_pipeline.transcribe as module

    clear_runtime_model_cache()
    local_model = tmp_path / "model"
    local_model.mkdir()
    loads = 0

    class FakeWhisperModel:
        def __init__(self, *_args, **_kwargs):
            nonlocal loads
            loads += 1

    monkeypatch.setenv("VID_PIPELINE_PERSISTENT_MODEL", "0")
    monkeypatch.setattr(
        module,
        "resolve_asr_model",
        lambda _name: ProvisionedAsrModel(
            local_model,
            {"name": "large-v3-turbo", "artifact_version": "v1", "asset_sha256": "x"},
            True,
        ),
    )
    monkeypatch.setattr(
        module,
        "_load_whisper",
        lambda: (SimpleNamespace(get_cuda_device_count=lambda: 0), FakeWhisperModel),
    )
    config = TranscriptionConfig(device="cpu", compute_type="int8")
    module.load_runtime_model(config)
    module.load_runtime_model(config)
    assert loads == 2
