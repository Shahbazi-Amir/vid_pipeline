"""Artifact storage abstraction."""

from __future__ import annotations

import shutil
from pathlib import Path
from typing import BinaryIO, Protocol


class ArtifactStore(Protocol):
    def save(self, source: Path, destination: str) -> str: ...

    def exists(self, destination: str) -> bool: ...

    def open(self, destination: str) -> BinaryIO: ...


class LocalArtifactStore:
    def __init__(self, root: str | Path) -> None:
        self.root = Path(root).resolve()
        self.root.mkdir(parents=True, exist_ok=True)

    def _path(self, destination: str) -> Path:
        candidate = (self.root / destination).resolve()
        if candidate != self.root and self.root not in candidate.parents:
            raise ValueError("destination must remain inside the artifact root")
        return candidate

    def save(self, source: Path, destination: str) -> str:
        target = self._path(destination)
        target.parent.mkdir(parents=True, exist_ok=True)
        if source.resolve() != target:
            shutil.copy2(source, target)
        return str(target)

    def exists(self, destination: str) -> bool:
        return self._path(destination).exists()

    def open(self, destination: str) -> BinaryIO:
        return self._path(destination).open("rb")
