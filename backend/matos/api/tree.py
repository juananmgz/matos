"""Endpoints de navegación jerárquica del archivo (geo_unit)."""

from __future__ import annotations

import sqlite3
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query

from ..index.queries import (
    get_geo,
    get_geo_by_path,
    items_of_geo,
    list_children,
    songs_of_geo,
    tree,
)
from .deps import get_conn

router = APIRouter(tags=["tree"])


@router.get("/api/tree")
def get_tree(conn: sqlite3.Connection = Depends(get_conn)) -> list[dict[str, Any]]:
    """Árbol completo CCAA → Provincia → Pueblo (incluye huérfanas)."""
    return tree(conn)


@router.get("/api/geo/by-path")
def get_by_path(
    path: str = Query(..., description="Path ltree, p.ej. andalucia.granada.pampaneira"),
    conn: sqlite3.Connection = Depends(get_conn),
) -> dict[str, Any]:
    geo = get_geo_by_path(conn, path)
    if geo is None:
        raise HTTPException(404, f"geo_unit no encontrado: {path}")
    return geo


@router.get("/api/geo/{geo_id}")
def get_geo_unit(
    geo_id: str,
    include: str = Query(
        "children,items,songs",
        description="Lista CSV: children,items,songs",
    ),
    conn: sqlite3.Connection = Depends(get_conn),
) -> dict[str, Any]:
    geo = get_geo(conn, geo_id)
    if geo is None:
        raise HTTPException(404, f"geo_unit no encontrado: {geo_id}")
    parts = {p.strip() for p in include.split(",") if p.strip()}
    if "children" in parts:
        geo["children"] = list_children(conn, geo_id)
    if "items" in parts:
        geo["items"] = items_of_geo(conn, geo_id)
    if "songs" in parts:
        geo["songs"] = songs_of_geo(conn, geo_id)
    return geo
