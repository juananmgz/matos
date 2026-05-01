"""StorageAdapter — abstracción sobre filesystem/S3."""

from __future__ import annotations

from .base import StorageAdapter
from .local import LocalStorage

__all__ = ["LocalStorage", "StorageAdapter"]
