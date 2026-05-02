"""Endpoints de streaming de media + resolución de embed para URLs externas.

- `GET /api/media/{item_id}` — sirve el binario local con HTTP Range (206).
  Falla 400 si el item es `kind=url` (no hay binario).
- `GET /api/media/{item_id}/embed` — para items con URL externa, devuelve
  `{type, platform, embed_url, original_url, thumbnail?}`.
- `GET /api/media/disco-track/{track_id}` — análogo para tracks de disco.

Range parsing: implementación mínima que cubre el caso típico de scrubbing
de audio (`bytes=START-`, `bytes=START-END`). Multi-range no soportado;
respondemos 416 si pide rango fuera del fichero.
"""

from __future__ import annotations

import mimetypes
import re
import sqlite3
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Depends, Header, HTTPException
from fastapi.responses import StreamingResponse

from ..index.queries import get_item
from .deps import get_archive_root, get_conn

router = APIRouter(tags=["media"])

CHUNK = 64 * 1024  # 64 KiB


# ─── Embed resolver ──────────────────────────────────────────────────────


_RESOLVERS: list[tuple[re.Pattern[str], str, str]] = [
    # (regex, platform, embed template — `{id}` se sustituye)
    (
        re.compile(r"^https?://open\.spotify\.com/(?:intl-[a-z]+/)?track/([A-Za-z0-9]+)"),
        "spotify",
        "https://open.spotify.com/embed/track/{id}",
    ),
    (
        re.compile(r"^https?://open\.spotify\.com/(?:intl-[a-z]+/)?album/([A-Za-z0-9]+)"),
        "spotify",
        "https://open.spotify.com/embed/album/{id}",
    ),
    (
        re.compile(r"^https?://open\.spotify\.com/(?:intl-[a-z]+/)?playlist/([A-Za-z0-9]+)"),
        "spotify",
        "https://open.spotify.com/embed/playlist/{id}",
    ),
    (
        re.compile(r"^https?://(?:www\.)?youtube\.com/watch\?(?:.*&)?v=([A-Za-z0-9_-]{11})"),
        "youtube",
        "https://www.youtube.com/embed/{id}",
    ),
    (
        re.compile(r"^https?://youtu\.be/([A-Za-z0-9_-]{11})"),
        "youtube",
        "https://www.youtube.com/embed/{id}",
    ),
    (
        re.compile(r"^https?://(?:www\.)?youtube\.com/embed/([A-Za-z0-9_-]{11})"),
        "youtube",
        "https://www.youtube.com/embed/{id}",
    ),
]


def resolve_embed(url: str) -> dict[str, Any]:
    """Detecta plataforma y devuelve descriptor para iframe.

    Para URLs no reconocidas devuelve `{type: "link", platform: "other", ...}`
    sin embed_url — el frontend renderiza un enlace simple.
    """
    for pattern, platform, template in _RESOLVERS:
        m = pattern.match(url)
        if m:
            return {
                "type": "iframe",
                "platform": platform,
                "embed_url": template.format(id=m.group(1)),
                "external_id": m.group(1),
                "original_url": url,
            }
    return {"type": "link", "platform": "other", "original_url": url}


# ─── Range helpers ───────────────────────────────────────────────────────


_RANGE_RE = re.compile(r"^bytes=(\d*)-(\d*)$")


def _parse_range(header: str, size: int) -> tuple[int, int] | None:
    """Parse `Range: bytes=START-END`. Devuelve (start, end inclusive) o None."""
    m = _RANGE_RE.match(header.strip())
    if not m:
        return None
    start_s, end_s = m.group(1), m.group(2)
    if start_s == "" and end_s == "":
        return None
    if start_s == "":
        # suffix: últimos N bytes
        n = int(end_s)
        if n <= 0:
            return None
        start = max(0, size - n)
        end = size - 1
    else:
        start = int(start_s)
        end = int(end_s) if end_s else size - 1
    if start > end or start >= size:
        return None
    end = min(end, size - 1)
    return start, end


def _stream_range(path: Path, start: int, end: int) -> Any:
    remaining = end - start + 1
    with path.open("rb") as f:
        f.seek(start)
        while remaining > 0:
            chunk = f.read(min(CHUNK, remaining))
            if not chunk:
                break
            remaining -= len(chunk)
            yield chunk


def _file_response(path: Path, mime: str, request_range: str | None) -> StreamingResponse:
    size = path.stat().st_size
    if request_range:
        rng = _parse_range(request_range, size)
        if rng is None:
            raise HTTPException(
                status_code=416,
                headers={"Content-Range": f"bytes */{size}"},
                detail="Rango inválido",
            )
        start, end = rng
        headers = {
            "Content-Range": f"bytes {start}-{end}/{size}",
            "Accept-Ranges": "bytes",
            "Content-Length": str(end - start + 1),
        }
        return StreamingResponse(
            _stream_range(path, start, end),
            status_code=206,
            media_type=mime,
            headers=headers,
        )
    headers = {"Accept-Ranges": "bytes", "Content-Length": str(size)}
    return StreamingResponse(
        _stream_range(path, 0, size - 1),
        media_type=mime,
        headers=headers,
    )


def _resolve_mime(stored: str | None, fname: str) -> str:
    if stored:
        return stored
    guess, _ = mimetypes.guess_type(fname)
    return guess or "application/octet-stream"


# ─── Endpoints ───────────────────────────────────────────────────────────


@router.get("/api/media/{item_id}")
def stream_item_media(
    item_id: str,
    range_header: str | None = Header(default=None, alias="Range"),
    conn: sqlite3.Connection = Depends(get_conn),
    archive_root: Path = Depends(get_archive_root),
) -> StreamingResponse:
    item = get_item(conn, item_id)
    if item is None:
        raise HTTPException(404, f"Item no encontrado: {item_id}")
    if item["kind"] == "url" or not item.get("file"):
        raise HTTPException(
            400,
            "Item sin fichero local — usa /api/media/{id}/embed para items URL",
        )
    fs_meta = Path(item["fs_path"])
    rel_bin = fs_meta.parent / item["file"]
    abs_bin = archive_root / rel_bin
    if not abs_bin.exists():
        raise HTTPException(404, f"Binario no encontrado: {rel_bin}")
    mime = _resolve_mime(item.get("mime_type"), item["file"])
    return _file_response(abs_bin, mime, range_header)


@router.get("/api/media/{item_id}/embed")
def get_item_embed(
    item_id: str,
    conn: sqlite3.Connection = Depends(get_conn),
) -> dict[str, Any]:
    item = get_item(conn, item_id)
    if item is None:
        raise HTTPException(404, f"Item no encontrado: {item_id}")
    url = item.get("url") or item["raw"].get("url")
    if not url:
        raise HTTPException(400, "Item sin URL — no hay embed disponible")
    out = resolve_embed(str(url))
    if seg := item["raw"].get("segment"):
        out["segment"] = {
            "offset_s": seg.get("offset_s"),
            "duration_s": seg.get("duration_s"),
            "label": seg.get("label"),
        }
    return out


@router.get("/api/media/disco-track/{track_id}")
def stream_disco_track(
    track_id: str,
    range_header: str | None = Header(default=None, alias="Range"),
    conn: sqlite3.Connection = Depends(get_conn),
    archive_root: Path = Depends(get_archive_root),
) -> StreamingResponse:
    row = conn.execute(
        "SELECT file, mime_type, fs_path FROM disco_track WHERE id = ?",
        (track_id,),
    ).fetchone()
    if row is None:
        raise HTTPException(404, f"Track no encontrado: {track_id}")
    # fs_path = discos/<artist>/(YYYY) titulo/metadatos/<n>.track.json
    # binario = parent.parent / file (sibling de _disco.json)
    fs_meta = Path(row["fs_path"])
    rel_bin = fs_meta.parent.parent / row["file"]
    abs_bin = archive_root / rel_bin
    if not abs_bin.exists():
        raise HTTPException(404, f"Binario no encontrado: {rel_bin}")
    mime = _resolve_mime(row["mime_type"], row["file"])
    return _file_response(abs_bin, mime, range_header)
