"""Interfaz abstracta `StorageAdapter`.

Define el contrato mínimo para leer/escribir el archivo. La implementación
local (`LocalStorage`) trabaja contra el filesystem; futuras implementaciones
(`S3Storage`, etc.) se enchufan sin tocar el resto del código.

Las rutas son `pathlib.PurePosixPath` relativas a la raíz del adaptador
(`/data/archivo` por defecto). Nunca absolutas, nunca con `..`.
"""

from __future__ import annotations

import hashlib
from abc import ABC, abstractmethod
from collections.abc import Iterator
from pathlib import PurePosixPath
from typing import IO


class StorageAdapter(ABC):
    """Contrato para acceso a la raíz del archivo."""

    @abstractmethod
    def exists(self, path: str | PurePosixPath) -> bool: ...

    @abstractmethod
    def is_dir(self, path: str | PurePosixPath) -> bool: ...

    @abstractmethod
    def list_dir(self, path: str | PurePosixPath) -> Iterator[PurePosixPath]:
        """Listado no recursivo. Devuelve rutas relativas a la raíz."""

    @abstractmethod
    def read_bytes(self, path: str | PurePosixPath) -> bytes: ...

    @abstractmethod
    def read_text(self, path: str | PurePosixPath) -> str: ...

    @abstractmethod
    def write_bytes(self, path: str | PurePosixPath, data: bytes) -> None: ...

    @abstractmethod
    def write_text(self, path: str | PurePosixPath, data: str) -> None: ...

    @abstractmethod
    def open_binary(self, path: str | PurePosixPath) -> IO[bytes]:
        """Abre en modo lectura binaria. Caller cierra."""

    @abstractmethod
    def size(self, path: str | PurePosixPath) -> int: ...

    @abstractmethod
    def walk(self, path: str | PurePosixPath) -> Iterator[PurePosixPath]:
        """Generador recursivo de ficheros (no directorios) bajo `path`."""

    def sha256(self, path: str | PurePosixPath, chunk_size: int = 1 << 20) -> str:
        """SHA-256 hex prefijado con `sha256:` — formato del campo del modelo."""
        h = hashlib.sha256()
        with self.open_binary(path) as f:
            while True:
                chunk = f.read(chunk_size)
                if not chunk:
                    break
                h.update(chunk)
        return f"sha256:{h.hexdigest()}"
