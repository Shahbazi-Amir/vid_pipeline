from __future__ import annotations

import hashlib
import io
import json
import tarfile
from pathlib import Path
from types import SimpleNamespace

import pytest

from vid_pipeline.asr_model import (
    AsrModelManager,
    AsrModelProvisioningError,
    ProvisionedAsrModel,
)
from vid_pipeline.transcribe import TranscriptionConfig, transcribe_audio


def _fixture(tmp_path: Path) -> tuple[Path, bytes, dict[str, bytes]]:
    files = {
        "model.bin": b"real-ct2-model-fixture",
        "config.json": b'{"model_type":"Whisper"}',
        "tokenizer.json": b"{}",
        "preprocessor_config.json": b"{}",
    }
    stream = io.BytesIO()
    with tarfile.open(fileobj=stream, mode="w:gz", format=tarfile.PAX_FORMAT) as bundle:
        for name, content in files.items():
            info = tarfile.TarInfo(f"model/{name}")
            info.size = len(content)
            info.mtime = 0
            bundle.addfile(info, io.BytesIO(content))
    archive = stream.getvalue()
    manifest = {
        "name": "large-v3-turbo",
        "artifact_version": "large-v3-turbo-ct2-v1",
        "release_tag": "asr-model-large-v3-turbo-ct2-v1",
        "asset_name": "large-v3-turbo-ct2-v1.tar.gz",
        "asset_url": "https://github.example/model.tar.gz",
        "asset_size": len(archive),
        "asset_sha256": hashlib.sha256(archive).hexdigest(),
        "files": [
            {"path": name, "size": len(content), "sha256": hashlib.sha256(content).hexdigest()}
            for name, content in files.items()
        ],
    }
    path = tmp_path / "manifest.json"
    path.write_text(json.dumps(manifest), encoding="utf-8")
    return path, archive, files


class _Response(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *_args):
        self.close()


def test_cache_miss_then_hit_never_redownloads(tmp_path: Path) -> None:
    manifest, archive, _ = _fixture(tmp_path)
    calls = 0

    def opener(_request, timeout):
        nonlocal calls
        assert timeout == 120
        calls += 1
        return _Response(archive)

    manager = AsrModelManager(manifest, tmp_path / "cache", opener)
    first = manager.provision("large-v3-turbo")
    second = manager.provision("large-v3-turbo")

    assert first.cache_hit is False
    assert second.cache_hit is True
    assert calls == 1
    assert (first.path / "model.bin").is_file()


def test_corrupt_cache_is_replaced(tmp_path: Path) -> None:
    manifest, archive, _ = _fixture(tmp_path)
    manager = AsrModelManager(manifest, tmp_path / "cache", lambda *_args, **_kwargs: _Response(archive))
    model = manager.provision("large-v3-turbo")
    (model.path / "model.bin").write_bytes(b"corrupt")

    restored = manager.provision("large-v3-turbo")

    assert restored.cache_hit is False
    assert (restored.path / "model.bin").read_bytes() == b"real-ct2-model-fixture"


def test_partial_download_is_replaced(tmp_path: Path) -> None:
    manifest, archive, _ = _fixture(tmp_path)
    cache = tmp_path / "cache"
    cache.mkdir()
    (cache / "large-v3-turbo-ct2-v1.tar.gz.part").write_bytes(b"partial")

    model = AsrModelManager(
        manifest, cache, lambda *_args, **_kwargs: _Response(archive)
    ).provision("large-v3-turbo")

    assert model.path.is_dir()
    assert not (cache / "large-v3-turbo-ct2-v1.tar.gz.part").exists()


def test_wrong_sha_hard_fails_without_fallback(tmp_path: Path) -> None:
    manifest, archive, _ = _fixture(tmp_path)
    data = json.loads(manifest.read_text(encoding="utf-8"))
    data["asset_sha256"] = "0" * 64
    manifest.write_text(json.dumps(data), encoding="utf-8")

    with pytest.raises(AsrModelProvisioningError, match="SHA-256 mismatch"):
        AsrModelManager(
            manifest, tmp_path / "cache", lambda *_args, **_kwargs: _Response(archive)
        ).provision("large-v3-turbo")


def test_missing_artifact_and_unsupported_model_fail_clearly(tmp_path: Path) -> None:
    manager = AsrModelManager(tmp_path / "missing.json", tmp_path / "cache")
    with pytest.raises(AsrModelProvisioningError, match="manifest"):
        manager.provision("large-v3-turbo")

    manifest, archive, _ = _fixture(tmp_path)
    manager = AsrModelManager(
        manifest, tmp_path / "cache", lambda *_args, **_kwargs: _Response(archive)
    )
    with pytest.raises(AsrModelProvisioningError, match="No project-controlled"):
        manager.provision("small")


def test_archive_path_traversal_is_rejected(tmp_path: Path) -> None:
    archive = tmp_path / "unsafe.tar.gz"
    with tarfile.open(archive, "w:gz") as bundle:
        info = tarfile.TarInfo("../escape")
        info.size = 1
        bundle.addfile(info, io.BytesIO(b"x"))
    with pytest.raises(AsrModelProvisioningError, match="Unsafe path"):
        AsrModelManager._safe_extract(archive, tmp_path / "extract")


def test_transcription_uses_local_path_with_hf_tokens_and_calls_forbidden(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    local_model = tmp_path / "local-ct2-model"
    local_model.mkdir()
    audio = tmp_path / "audio.wav"
    audio.write_bytes(b"fixture")
    received: list[str] = []

    class FakeWhisperModel:
        def __init__(self, path: str, **_kwargs):
            received.append(path)

        def transcribe(self, *_args, **_kwargs):
            return iter(()), SimpleNamespace(language="fa", language_probability=1.0, duration=1.0)

    def forbidden(*_args, **_kwargs):
        raise AssertionError("Hugging Face runtime call attempted")

    import vid_pipeline.transcribe as transcribe_module

    monkeypatch.delenv("HF_TOKEN", raising=False)
    monkeypatch.delenv("HUGGING_FACE_HUB_TOKEN", raising=False)
    monkeypatch.setattr(
        transcribe_module,
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
        transcribe_module,
        "_load_whisper",
        lambda: (SimpleNamespace(get_cuda_device_count=lambda: 0), FakeWhisperModel),
    )
    monkeypatch.setitem(
        __import__("sys").modules,
        "huggingface_hub",
        SimpleNamespace(
            snapshot_download=forbidden,
            hf_hub_download=forbidden,
            model_info=forbidden,
        ),
    )

    result = transcribe_audio(
        audio,
        tmp_path / "result.json",
        tmp_path / "result.md",
        TranscriptionConfig(model="large-v3-turbo", device="cpu", compute_type="int8"),
    )

    assert received == [str(local_model)]
    assert result["asr_model_integrity_ok"] is True
    assert result["asr_model_source"] == "github-release"
