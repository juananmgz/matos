"""Endpoints de items (lectura)."""

from __future__ import annotations

import sqlite3
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query

from ..index.queries import get_item, list_items, search_items
from ..models.item import EnrichmentStatus, ItemKind, Platform, SourceType
from .deps import Pagination, get_conn, pagination

router = APIRouter(tags=["items"])


@router.get("/api/items")
def list_items_endpoint(
    geo_id: str | None = None,
    song_id: str | None = None,
    kind: ItemKind | None = None,
    status: EnrichmentStatus | None = None,
    platform: Platform | None = None,
    source_type: SourceType | None = None,
    has_external: bool | None = None,
    q: str | None = Query(None, description="Búsqueda FTS5 sobre título/intérpretes/tags"),
    pag: Pagination = Depends(pagination),
    conn: sqlite3.Connection = Depends(get_conn),
) -> dict[str, Any]:
    if q:
        rows = search_items(conn, q, limit=pag.limit + pag.offset)
        return {
            "items": rows[pag.offset : pag.offset + pag.limit],
            "total": len(rows),
            "limit": pag.limit,
            "offset": pag.offset,
        }
    rows, total = list_items(
        conn,
        geo_id=geo_id,
        song_id=song_id,
        kind=kind.value if kind else None,
        status=status.value if status else None,
        platform=platform.value if platform else None,
        source_type=source_type.value if source_type else None,
        has_external=has_external,
        limit=pag.limit,
        offset=pag.offset,
    )
    return {"items": rows, "total": total, "limit": pag.limit, "offset": pag.offset}


@router.get("/api/items/{item_id}")
def get_item_endpoint(
    item_id: str,
    conn: sqlite3.Connection = Depends(get_conn),
) -> dict[str, Any]:
    item = get_item(conn, item_id)
    if item is None:
        raise HTTPException(404, f"Item no encontrado: {item_id}")
    return item
