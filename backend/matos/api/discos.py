"""Endpoints de discos (lectura)."""

from __future__ import annotations

import sqlite3
from typing import Any

from fastapi import APIRouter, Depends, HTTPException

from ..index.queries import get_disco, list_discos, segments_of_track, tracks_of_disco
from .deps import Pagination, get_conn, pagination

router = APIRouter(tags=["discos"])


@router.get("/api/discos")
def list_discos_endpoint(
    pag: Pagination = Depends(pagination),
    conn: sqlite3.Connection = Depends(get_conn),
) -> dict[str, Any]:
    rows = list_discos(conn)
    total = len(rows)
    return {
        "items": rows[pag.offset : pag.offset + pag.limit],
        "total": total,
        "limit": pag.limit,
        "offset": pag.offset,
    }


@router.get("/api/discos/{disco_id}")
def get_disco_endpoint(
    disco_id: str,
    conn: sqlite3.Connection = Depends(get_conn),
) -> dict[str, Any]:
    disco = get_disco(conn, disco_id)
    if disco is None:
        raise HTTPException(404, f"Disco no encontrado: {disco_id}")
    return disco


@router.get("/api/tracks/{track_id}/segments")
def list_track_segments(
    track_id: str,
    conn: sqlite3.Connection = Depends(get_conn),
) -> list[dict[str, Any]]:
    return segments_of_track(conn, track_id)


@router.get("/api/discos/{disco_id}/tracks")
def list_disco_tracks(
    disco_id: str,
    conn: sqlite3.Connection = Depends(get_conn),
) -> list[dict[str, Any]]:
    if get_disco(conn, disco_id) is None:
        raise HTTPException(404, f"Disco no encontrado: {disco_id}")
    return tracks_of_disco(conn, disco_id)
