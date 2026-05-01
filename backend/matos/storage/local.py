"""Implementación filesystem de `StorageAdapter`."""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path, PurePosixPath
from typing import IO

from .base import StorageAdapter


class LocalStorage(StorageAdapter):
    """Adaptador sobre el filesystem local. Raíz fijada al construir."""

    def __init__(self, root: Path | str) -> None:
        self._root = Path(root).resolve()
        if self._root.exists() and not self._root.is_dir():
            raise NotADirectoryError(f"{self._root} no es un directorio")

    @property
    def root(self) -> Path:
        return self._root

    # ── helpers internos ───────────────────────────────────────────────────

    def _abs(self, path: str | PurePosixPath) -> Path:
        p = PurePosixPath(path)
        if p.is_absolute() or any(part == ".." for part in p.parts):
            raise ValueError(f"ruta no admitida: {path!r}")
        return self._root / p

    def _rel(self, abs_path: Path) -> PurePosixPath:
        return PurePosixPath(abs_path.relative_to(self._root).as_posix())

    # ── interfaz ───────────────────────────────────────────────────────────

    def exists(self, path: str | PurePosixPath) -> bool:
        return self._abs(path).exists()

    def is_dir(self, path: str | PurePosixPath) -> bool:
        return self._abs(path).is_dir()

    def list_dir(self, path: str | PurePosixPath) -> Iterator[PurePosixPath]:
        target = self._abs(path)
        if not target.exists():
            return
        for child in sorted(target.iterdir()):
            yield self._rel(child)

    def read_bytes(self, path: str | PurePosixPath) -> bytes:
        return self._abs(path).read_bytes()

    def read_text(self, path: str | PurePosixPath) -> str:
        return self._abs(path).read_text(encoding="utf-8")

    def write_bytes(self, path: str | PurePosixPath, data: bytes) -> None:
        target = self._abs(path)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)

    def write_text(self, path: str | PurePosixPath, data: str) -> None:
        target = self._abs(path)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(data, encoding="utf-8")

    def open_binary(self, path: str | PurePosixPath) -> IO[bytes]:
        return self._abs(path).open("rb")

    def size(self, path: str | PurePosixPath) -> int:
        return self._abs(path).stat().st_size

    def walk(self, path: str | PurePosixPath) -> Iterator[PurePosixPath]:
        base = self._abs(path)
        if not base.exists():
            return
        for sub in sorted(base.rglob("*")):
            if sub.is_file():
                yield self._rel(sub)
