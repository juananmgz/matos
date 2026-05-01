"""Funciones de consulta sobre el índice SQLite (sync, stdlib `sqlite3`).

Pensadas para uso síncrono desde scripts/CLI y como base de la capa async
de la API (fase 3 envuelve en `aiosqlite` o usa `run_in_threadpool`).

Conexión: cada función abre su propia conexión read-only para mantenerlas
puras. Para batch de queries en un mismo handler, usar `connect()`.
"""

from __future__ import annotations

import json
import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Any


@contextmanager
def connect(db_path: Path | str, *, read_only: bool = True) -> Iterator[sqlite3.Connection]:
    """Conexión SQLite con `row_factory` configurado.

    Modo read-only por defecto: la API nunca escribe. Para tests se puede
    pasar `read_only=False`.
    """
    db_path = Path(db_path)
    if read_only:
        uri = f"file:{db_path}?mode=ro"
        conn = sqlite3.connect(uri, uri=True)
    else:
        conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
    finally:
        conn.close()


# ─── geo ──────────────────────────────────────────────────────────────────


def list_ccaa(conn: sqlite3.Connection) -> list[dict[str, Any]]:
    rows = conn.execute("SELECT * FROM geo_unit WHERE level = 'ccaa' ORDER BY nombre").fetchall()
    return [_geo_row(r) for r in rows]


def list_children(conn: sqlite3.Connection, parent_id: str) -> list[dict[str, Any]]:
    rows = conn.execute(
        "SELECT * FROM geo_unit WHERE parent_id = ? ORDER BY nombre",
        (parent_id,),
    ).fetchall()
    return [_geo_row(r) for r in rows]


def get_geo(conn: sqlite3.Connection, geo_id: str) -> dict[str, Any] | None:
    row = conn.execute("SELECT * FROM geo_unit WHERE id = ?", (geo_id,)).fetchone()
    return _geo_row(row) if row else None


def get_geo_by_path(conn: sqlite3.Connection, path: str) -> dict[str, Any] | None:
    row = conn.execute("SELECT * FROM geo_unit WHERE path = ?", (path,)).fetchone()
    return _geo_row(row) if row else None


def tree(conn: sqlite3.Connection) -> list[dict[str, Any]]:
    """Árbol completo (CCAA → Provincias → Pueblos) anidado."""
    by_parent: dict[str | None, list[dict[str, Any]]] = {}
    for r in conn.execute("SELECT * FROM geo_unit ORDER BY level, nombre").fetchall():
        d = _geo_row(r)
        by_parent.setdefault(d["parent_id"], []).append(d)

    def attach(node: dict[str, Any]) -> dict[str, Any]:
        children = by_parent.get(node["id"], [])
        node["children"] = [attach(c) for c in children]
        return node

    return [attach(c) for c in by_parent.get(None, [])]


# ─── items ────────────────────────────────────────────────────────────────


def get_item(conn: sqlite3.Connection, item_id: str) -> dict[str, Any] | None:
    row = conn.execute("SELECT * FROM item WHERE id = ?", (item_id,)).fetchone()
    return _item_row(row) if row else None


def items_of_geo(conn: sqlite3.Connection, geo_id: str) -> list[dict[str, Any]]:
    rows = conn.execute(
        "SELECT * FROM item WHERE geo_id = ? ORDER BY title",
        (geo_id,),
    ).fetchall()
    return [_item_row(r) for r in rows]


def items_of_song(conn: sqlite3.Connection, song_id: str) -> list[dict[str, Any]]:
    rows = conn.execute(
        "SELECT * FROM item WHERE song_id = ? ORDER BY created_at",
        (song_id,),
    ).fetchall()
    return [_item_row(r) for r in rows]


def search_items(conn: sqlite3.Connection, query: str, limit: int = 50) -> list[dict[str, Any]]:
    """FTS5 sobre title/interpretes/tags."""
    rows = conn.execute(
        "SELECT item.* FROM item_fts "
        "JOIN item ON item.rowid = item_fts.rowid "
        "WHERE item_fts MATCH ? "
        "ORDER BY rank LIMIT ?",
        (query, limit),
    ).fetchall()
    return [_item_row(r) for r in rows]


# ─── songs ────────────────────────────────────────────────────────────────


def get_song(conn: sqlite3.Connection, song_id: str) -> dict[str, Any] | None:
    row = conn.execute("SELECT * FROM song WHERE id = ?", (song_id,)).fetchone()
    if row is None:
        return None
    song = _song_row(row)
    song["relations"] = [
        dict(r)
        for r in conn.execute(
            "SELECT type, src_item, tgt_item, notes FROM relation WHERE song_id = ?",
            (song_id,),
        ).fetchall()
    ]
    return song


def list_songs(conn: sqlite3.Connection) -> list[dict[str, Any]]:
    rows = conn.execute("SELECT * FROM song ORDER BY title").fetchall()
    return [_song_row(r) for r in rows]


# ─── meta ────────────────────────────────────────────────────────────────


def get_meta(conn: sqlite3.Connection) -> dict[str, str]:
    return {row["key"]: row["value"] for row in conn.execute("SELECT * FROM meta").fetchall()}


# ─── row helpers ─────────────────────────────────────────────────────────


def _geo_row(row: sqlite3.Row) -> dict[str, Any]:
    d = dict(row)
    d["extra"] = json.loads(d.pop("extra_json"))
    return d


def _item_row(row: sqlite3.Row) -> dict[str, Any]:
    d = dict(row)
    d["tags"] = json.loads(d["tags"]) if d.get("tags") else []
    d["raw"] = json.loads(d.pop("raw_json"))
    return d


def _song_row(row: sqlite3.Row) -> dict[str, Any]:
    d = dict(row)
    d["title_variants"] = json.loads(d["title_variants"]) if d.get("title_variants") else []
    d["tags"] = json.loads(d["tags"]) if d.get("tags") else []
    return d
