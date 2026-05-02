"""Dependencias FastAPI compartidas: conexión SQLite read-only y paginación."""

from __future__ import annotations

import sqlite3
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path

from fastapi import Depends, HTTPException, Query

from ..config import settings
from ..index.queries import connect


def get_db_path() -> Path:
    """Override-able para tests (vía `app.dependency_overrides`)."""
    return settings.index_path


def get_conn(db_path: Path = Depends(get_db_path)) -> Iterator[sqlite3.Connection]:
    if not db_path.exists():
        raise HTTPException(
            status_code=503,
            detail=f"Índice no encontrado en {db_path}. Ejecuta `make reindex`.",
        )
    with connect(db_path) as conn:
        yield conn


@dataclass
class Pagination:
    limit: int
    offset: int


def pagination(
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
) -> Pagination:
    return Pagination(limit=limit, offset=offset)
