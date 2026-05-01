"""Índice SQLite derivado del filesystem.

`builder.py`  → walker que construye el índice desde cero.
`queries.py`  → consultas sobre el índice (sync, stdlib `sqlite3`).
`schema.sql`  → DDL.
"""

from __future__ import annotations

from .builder import IndexReport, build_index, validate_archive

__all__ = ["IndexReport", "build_index", "validate_archive"]
