"""Integrity-checked, project-controlled faster-whisper model provisioning."""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import tarfile
import tempfile
import threading
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from vid_pipeline.errors import ExternalToolError

DEFAULT_MANIFEST = Path(__file__).resolve().parents[2] / "models/asr/large-v3-turbo-ct2-v1.json"
DEFAULT_CACHE = Path.home() / ".cache/vid-pipeline/asr"
_VALIDATED_MODEL_SIGNATURES: dict[str, tuple[tuple[str, int, int], ...]] = {}
_VALIDATION_LOCK = threading.Lock()


class AsrModelProvisioningError(ExternalToolError):
    """Raised when the pinned project model cannot be provisioned safely."""


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _model_signature(path: Path, manifest: dict[str, Any]) -> tuple[tuple[str, int, int], ...] | None:
    rows: list[tuple[str, int, int]] = []
    for item in manifest["files"]:
        candidate = path / item["path"]
        if not candidate.is_file():
            return None
        stat = candidate.stat()
        if stat.st_size != int(item["size"]):
            return None
        rows.append((str(item["path"]), stat.st_size, stat.st_mtime_ns))
    return tuple(rows)


@dataclass(frozen=True, slots=True)
class ProvisionedAsrModel:
    path: Path
    manifest: dict[str, Any]
    cache_hit: bool

    @property
    def diagnostics(self) -> dict[str, Any]:
        return {
            "asr_model_name": self.manifest["name"],
            "asr_model_version": self.manifest["artifact_version"],
            "asr_model_path": str(self.path),
            "asr_model_source": "github-release",
            "asr_model_artifact_sha256": self.manifest["asset_sha256"],
            "asr_model_integrity_ok": True,
            "asr_model_cache_hit": self.cache_hit,
        }


class AsrModelManager:
    """Provision a pinned CT2 model without any Hugging Face runtime fallback.

    A cached model is fully SHA-256 validated once per worker process. Repeated
    jobs reuse that validation while file size/mtime signatures are unchanged,
    avoiding a full re-hash of the ~1.6 GB model on every transcription.
    """

    def __init__(
        self,
        manifest_path: str | Path | None = None,
        cache_root: str | Path | None = None,
        opener: Any = None,
    ) -> None:
        self.manifest_path = Path(
            manifest_path or os.environ.get("VID_PIPELINE_ASR_MANIFEST", DEFAULT_MANIFEST)
        )
        self.cache_root = Path(
            cache_root or os.environ.get("VID_PIPELINE_ASR_CACHE", DEFAULT_CACHE)
        )
        self.opener = opener or urllib.request.urlopen

    def _manifest(self) -> dict[str, Any]:
        try:
            data = json.loads(self.manifest_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise AsrModelProvisioningError(
                f"Project ASR manifest is unavailable or invalid: {self.manifest_path}"
            ) from exc
        required = {
            "name", "artifact_version", "release_tag", "asset_name", "asset_url",
            "asset_size", "asset_sha256", "files",
        }
        missing = sorted(required - data.keys())
        if missing:
            raise AsrModelProvisioningError(f"Project ASR manifest missing fields: {missing}")
        return data

    @staticmethod
    def _validate_model(path: Path, manifest: dict[str, Any]) -> bool:
        signature = _model_signature(path, manifest)
        if signature is None:
            return False
        for item in manifest["files"]:
            if _sha256(path / item["path"]) != item["sha256"]:
                return False
        return True

    @staticmethod
    def _validation_key(path: Path, manifest: dict[str, Any]) -> str:
        return f"{path.resolve()}::{manifest['artifact_version']}::{manifest['asset_sha256']}"

    @classmethod
    def _validate_cached_model(cls, path: Path, manifest: dict[str, Any]) -> bool:
        signature = _model_signature(path, manifest)
        if signature is None:
            return False
        key = cls._validation_key(path, manifest)
        with _VALIDATION_LOCK:
            if _VALIDATED_MODEL_SIGNATURES.get(key) == signature:
                return True
        if not cls._validate_model(path, manifest):
            with _VALIDATION_LOCK:
                _VALIDATED_MODEL_SIGNATURES.pop(key, None)
            return False
        with _VALIDATION_LOCK:
            _VALIDATED_MODEL_SIGNATURES[key] = signature
        return True

    @staticmethod
    def _safe_extract(archive: Path, destination: Path) -> None:
        destination_resolved = destination.resolve()
        with tarfile.open(archive, "r:gz") as bundle:
            for member in bundle.getmembers():
                target = (destination / member.name).resolve()
                if target != destination_resolved and destination_resolved not in target.parents:
                    raise AsrModelProvisioningError("Unsafe path in ASR model archive")
                if member.issym() or member.islnk():
                    raise AsrModelProvisioningError("Links are forbidden in ASR model archive")
            bundle.extractall(destination, filter="data")

    def provision(self, model_name: str) -> ProvisionedAsrModel:
        manifest = self._manifest()
        if model_name not in {manifest["name"], "large-v3-turbo"}:
            raise AsrModelProvisioningError(
                f"No project-controlled ASR artifact is configured for model {model_name!r}"
            )
        version_dir = self.cache_root / manifest["artifact_version"]
        model_dir = version_dir / "model"
        if self._validate_cached_model(model_dir, manifest):
            return ProvisionedAsrModel(model_dir, manifest, True)

        self.cache_root.mkdir(parents=True, exist_ok=True)
        if version_dir.exists():
            quarantine = version_dir.with_name(version_dir.name + ".corrupt")
            shutil.rmtree(quarantine, ignore_errors=True)
            os.replace(version_dir, quarantine)

        archive = self.cache_root / manifest["asset_name"]
        partial = archive.with_suffix(archive.suffix + ".part")
        partial.unlink(missing_ok=True)
        try:
            request = urllib.request.Request(
                manifest["asset_url"],
                headers={"Accept": "application/octet-stream", "User-Agent": "vid-pipeline"},
            )
            with self.opener(request, timeout=120) as response, partial.open("wb") as output:
                while chunk := response.read(1024 * 1024):
                    output.write(chunk)
            if partial.stat().st_size != int(manifest["asset_size"]):
                raise AsrModelProvisioningError("ASR model artifact size mismatch")
            if _sha256(partial) != manifest["asset_sha256"]:
                raise AsrModelProvisioningError("ASR model artifact SHA-256 mismatch")
            os.replace(partial, archive)
            temporary = Path(tempfile.mkdtemp(prefix="asr-extract-", dir=self.cache_root))
            try:
                self._safe_extract(archive, temporary)
                extracted = temporary / "model"
                if not self._validate_model(extracted, manifest):
                    raise AsrModelProvisioningError("Extracted ASR model failed integrity checks")
                os.replace(temporary, version_dir)
                # Record the installed model's signature only after verified files
                # have reached their final path.
                self._validate_cached_model(model_dir, manifest)
            except Exception:
                shutil.rmtree(temporary, ignore_errors=True)
                raise
        except AsrModelProvisioningError:
            partial.unlink(missing_ok=True)
            archive.unlink(missing_ok=True)
            raise
        except Exception as exc:
            partial.unlink(missing_ok=True)
            raise AsrModelProvisioningError(
                f"Project ASR artifact download failed: {exc}"
            ) from exc
        return ProvisionedAsrModel(model_dir, manifest, False)


def resolve_asr_model(model_name: str) -> ProvisionedAsrModel:
    path = Path(model_name)
    if path.is_dir():
        return ProvisionedAsrModel(
            path,
            {
                "name": path.name,
                "artifact_version": "external-local-path",
                "asset_sha256": "external-local-path",
            },
            True,
        )
    return AsrModelManager().provision(model_name)
