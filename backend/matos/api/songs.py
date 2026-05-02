"""Endpoints de songs (lectura)."""

from __future__ import annotations

import sqlite3
from typing import Any

from fastapi import APIRouter, Depends, HTTPException

from ..index.queries import (
    disco_segments_of_song,
    get_song,
    items_of_song,
    list_songs,
)
from .deps import Pagination, get_conn, pagination

router = APIRouter(tags=["songs"])


@router.get("/api/songs")
def list_songs_endpoint(
    geo_id: str | None = None,
    original_recording_missing: bool | None = None,
    pag: Pagination = Depends(pagination),
    conn: sqlite3.Connection = Depends(get_conn),
) -> dict[str, Any]:
    rows, total = list_songs(
        conn,
        geo_id=geo_id,
        original_recording_missing=original_recording_missing,
        limit=pag.limit,
        offset=pag.offset,
    )
    return {"items": rows, "total": total, "limit": pag.limit, "offset": pag.offset}


@router.get("/api/songs/{song_id}")
def get_song_endpoint(
    song_id: str,
    conn: sqlite3.Connection = Depends(get_conn),
) -> dict[str, Any]:
    song = get_song(conn, song_id)
    if song is None:
        raise HTTPException(404, f"Song no encontrada: {song_id}")
    song["items"] = items_of_song(conn, song_id)
    song["disco_segments"] = disco_segments_of_song(conn, song_id)
    return song
