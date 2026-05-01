"""Tests del adaptador de almacenamiento."""

from __future__ import annotations

import hashlib
from pathlib import Path

import pytest

from matos.storage import LocalStorage


@pytest.fixture
def storage(tmp_path: Path) -> LocalStorage:
    return LocalStorage(tmp_path)


class TestLocalStorage:
    def test_write_and_read_text(self, storage: LocalStorage) -> None:
        storage.write_text("hello.txt", "hola")
        assert storage.exists("hello.txt")
        assert storage.read_text("hello.txt") == "hola"

    def test_write_creates_parent(self, storage: LocalStorage) -> None:
        storage.write_text("a/b/c.txt", "x")
        assert storage.exists("a/b/c.txt")
        assert storage.is_dir("a/b")

    def test_list_dir_sorted(self, storage: LocalStorage) -> None:
        for n in ["c.txt", "a.txt", "b.txt"]:
            storage.write_text(n, "")
        names = [p.name for p in storage.list_dir(".")]
        assert names == sorted(names)

    def test_walk_only_files(self, storage: LocalStorage) -> None:
        storage.write_text("a/b.txt", "x")
        storage.write_text("a/c/d.txt", "y")
        files = sorted(p.as_posix() for p in storage.walk("."))
        assert files == ["a/b.txt", "a/c/d.txt"]

    def test_sha256_matches_stdlib(self, storage: LocalStorage) -> None:
        data = b"abc" * 1000
        storage.write_bytes("blob.bin", data)
        expected = "sha256:" + hashlib.sha256(data).hexdigest()
        assert storage.sha256("blob.bin") == expected

    def test_rejects_absolute_path(self, storage: LocalStorage) -> None:
        with pytest.raises(ValueError, match="ruta no admitida"):
            storage.exists("/etc/passwd")

    def test_rejects_dotdot(self, storage: LocalStorage) -> None:
        with pytest.raises(ValueError, match="ruta no admitida"):
            storage.read_text("../escape.txt")

    def test_size(self, storage: LocalStorage) -> None:
        storage.write_bytes("x.bin", b"1234567")
        assert storage.size("x.bin") == 7
