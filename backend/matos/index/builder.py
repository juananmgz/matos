"""Walker + writer del índice SQLite.

Recorre el filesystem `archivo/` vía `StorageAdapter`, valida cada JSON
contra el modelo Pydantic correspondiente, e inserta una fila en la tabla
SQLite asociada. Construcción atómica: se escribe a un fichero temporal y
se renombra al final (rebuild es siempre desde cero).

Uso:
    from matos.index.builder import build_index, validate_archive

    report = build_index(storage, db_path)         # rebuild completo
    report = validate_archive(storage)             # solo validación
"""

from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path, PurePosixPath
from typing import TYPE_CHECKING, Any

from pydantic import ValidationError

from ..models import (
    CCAA,
    SCHEMA_VERSION,
    ArchiveIndex,
    Item,
    ItemKind,
    Provincia,
    Pueblo,
    Song,
)

if TYPE_CHECKING:
    from ..storage import StorageAdapter

SCHEMA_FILE = Path(__file__).parent / "schema.sql"


# ─── Reporting ────────────────────────────────────────────────────────────


@dataclass
class IndexReport:
    archive_meta: ArchiveIndex | None = None
    ccaa: int = 0
    provincias: int = 0
    pueblos: int = 0
    items: int = 0
    songs: int = 0
    relations: int = 0
    errors: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.errors


# ─── Helpers de carga y validación ────────────────────────────────────────


def _load_json(storage: StorageAdapter, path: PurePosixPath) -> Any:
    return json.loads(storage.read_text(path))


def _slug(p: PurePosixPath) -> str:
    return p.name


def _path_dotted(parts: list[str]) -> str:
    return ".".join(parts)


def _interpretes_text(item: Item) -> str:
    parts = list(item.context.interprete)
    if item.context.recopilador:
        parts.extend(item.context.recopilador)
    if item.source.release and item.source.release.artist:
        parts.append(item.source.release.artist)
    return " | ".join(p for p in parts if p)


def _platform(item: Item) -> str | None:
    if item.source.release and item.source.release.platform:
        return item.source.release.platform.value
    if item.source.broadcast and item.source.broadcast.platform:
        return item.source.broadcast.platform.value
    return None


# ─── Validación pura (sin SQLite) ─────────────────────────────────────────


def validate_archive(storage: StorageAdapter) -> IndexReport:
    """Recorre y valida todos los JSON sin escribir índice.

    Útil como `matos validate` y como check en CI.
    """
    report = IndexReport()
    _walk(storage, report, write=None)
    return report


# ─── Construcción del índice ──────────────────────────────────────────────


def build_index(storage: StorageAdapter, db_path: Path) -> IndexReport:
    """Reconstruye el índice SQLite desde cero.

    Estrategia: escribir a `<db_path>.tmp`, hacer commit, mover sobre el
    destino. Garantiza que un fallo a mitad de build no deja un índice
    corrupto en producción.
    """
    db_path = Path(db_path)
    db_path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = db_path.with_suffix(db_path.suffix + ".tmp")
    if tmp_path.exists():
        tmp_path.unlink()

    conn = sqlite3.connect(tmp_path)
    try:
        conn.executescript(SCHEMA_FILE.read_text(encoding="utf-8"))
        report = IndexReport()
        _walk(storage, report, write=conn)
        if report.ok:
            _write_meta(conn, report)
            conn.commit()
        else:
            conn.rollback()
    finally:
        conn.close()

    if report.ok:
        tmp_path.replace(db_path)
    else:
        tmp_path.unlink(missing_ok=True)

    return report


def _write_meta(conn: sqlite3.Connection, report: IndexReport) -> None:
    now = datetime.now(UTC).isoformat()
    rows = [
        ("schema_version", SCHEMA_VERSION),
        ("built_at", now),
        ("ccaa_count", str(report.ccaa)),
        ("provincias_count", str(report.provincias)),
        ("pueblos_count", str(report.pueblos)),
        ("items_count", str(report.items)),
        ("songs_count", str(report.songs)),
        ("relations_count", str(report.relations)),
    ]
    if report.archive_meta:
        rows.append(("archive_name", report.archive_meta.archive_name or ""))
    conn.executemany(
        "INSERT OR REPLACE INTO meta(key, value) VALUES (?, ?)",
        rows,
    )


# ─── Walker común ─────────────────────────────────────────────────────────
#
# Recorre archivo/ y, para cada entidad, llama a `write` (insertar en SQLite)
# si está presente. En modo validación, `write` es None y solo se validan los
# Pydantic.


def _walk(
    storage: StorageAdapter,
    report: IndexReport,
    write: sqlite3.Connection | None,
) -> None:
    root = PurePosixPath(".")

    # _index.json (opcional, pero recomendado)
    idx_path = PurePosixPath("_index.json")
    if storage.exists(idx_path):
        try:
            report.archive_meta = ArchiveIndex.model_validate(_load_json(storage, idx_path))
        except (ValidationError, json.JSONDecodeError) as e:
            report.errors.append(f"_index.json: {e}")

    # CCAA folders
    for ccaa_dir in storage.list_dir(root):
        if not storage.is_dir(ccaa_dir) or ccaa_dir.name.startswith((".", "_")):
            continue
        ccaa = _ingest_ccaa(storage, ccaa_dir, report, write)
        if ccaa is None:
            continue

        for prov_dir in storage.list_dir(ccaa_dir):
            if not storage.is_dir(prov_dir) or prov_dir.name.startswith((".", "_")):
                continue
            prov = _ingest_provincia(storage, prov_dir, ccaa, report, write)
            if prov is None:
                continue

            for pueblo_dir in storage.list_dir(prov_dir):
                if not storage.is_dir(pueblo_dir) or pueblo_dir.name.startswith((".", "_")):
                    continue
                _ingest_pueblo(storage, pueblo_dir, prov, report, write)


# ─── Ingesta por nivel ────────────────────────────────────────────────────


def _ingest_ccaa(
    storage: StorageAdapter,
    folder: PurePosixPath,
    report: IndexReport,
    write: sqlite3.Connection | None,
) -> CCAA | None:
    meta = folder / "_ccaa.json"
    if not storage.exists(meta):
        report.errors.append(f"{folder}: falta _ccaa.json")
        return None
    try:
        ccaa = CCAA.model_validate(_load_json(storage, meta))
    except (ValidationError, json.JSONDecodeError) as e:
        report.errors.append(f"{meta}: {e}")
        return None

    report.ccaa += 1
    if write is not None:
        write.execute(
            "INSERT INTO geo_unit(id, level, nombre, parent_id, path, slug, codigo, fs_path, extra_json) "
            "VALUES (?, ?, ?, NULL, ?, ?, ?, ?, ?)",
            (
                str(ccaa.id),
                ccaa.level.value,
                ccaa.nombre,
                _slug(folder),
                _slug(folder),
                ccaa.codigo,
                str(folder),
                json.dumps({"notas": ccaa.notas}, ensure_ascii=False),
            ),
        )
    return ccaa


def _ingest_provincia(
    storage: StorageAdapter,
    folder: PurePosixPath,
    ccaa: CCAA,
    report: IndexReport,
    write: sqlite3.Connection | None,
) -> Provincia | None:
    meta = folder / "_provincia.json"
    if not storage.exists(meta):
        report.errors.append(f"{folder}: falta _provincia.json")
        return None
    try:
        prov = Provincia.model_validate(_load_json(storage, meta))
    except (ValidationError, json.JSONDecodeError) as e:
        report.errors.append(f"{meta}: {e}")
        return None

    report.provincias += 1
    if write is not None:
        path = _path_dotted([folder.parent.name, folder.name])
        write.execute(
            "INSERT INTO geo_unit(id, level, nombre, parent_id, path, slug, codigo, fs_path, extra_json) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                str(prov.id),
                prov.level.value,
                prov.nombre,
                str(ccaa.id),
                path,
                _slug(folder),
                prov.codigo_ine,
                str(folder),
                json.dumps({"notas": prov.notas}, ensure_ascii=False),
            ),
        )
    return prov


def _ingest_pueblo(
    storage: StorageAdapter,
    folder: PurePosixPath,
    prov: Provincia,
    report: IndexReport,
    write: sqlite3.Connection | None,
) -> None:
    meta = folder / "_pueblo.json"
    if not storage.exists(meta):
        report.errors.append(f"{folder}: falta _pueblo.json")
        return
    try:
        pueblo = Pueblo.model_validate(_load_json(storage, meta))
    except (ValidationError, json.JSONDecodeError) as e:
        report.errors.append(f"{meta}: {e}")
        return

    report.pueblos += 1
    # path ltree-like derivado de las carpetas, no del nombre legible
    # (que puede llevar acentos / espacios).
    path = _path_dotted([folder.parent.parent.name, folder.parent.name, folder.name])

    if write is not None:
        extra = {
            "notas": pueblo.notas,
            "comarca": pueblo.comarca.model_dump(mode="json") if pueblo.comarca else None,
            "subcomarca": pueblo.subcomarca.model_dump(mode="json") if pueblo.subcomarca else None,
            "centroid": pueblo.centroid.model_dump(mode="json") if pueblo.centroid else None,
        }
        write.execute(
            "INSERT INTO geo_unit(id, level, nombre, parent_id, path, slug, codigo, fs_path, extra_json) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                str(pueblo.id),
                pueblo.level.value,
                pueblo.nombre,
                str(prov.id),
                path,
                _slug(folder),
                pueblo.codigo_ine,
                str(folder),
                json.dumps(extra, ensure_ascii=False),
            ),
        )

    # Songs antes que items: item.song_id referencia song(id) y la FK es
    # validada en cada INSERT.
    songs_dir = folder / "songs"
    if storage.exists(songs_dir) and storage.is_dir(songs_dir):
        for child in storage.list_dir(songs_dir):
            if child.name.endswith(".song.json"):
                _ingest_song(storage, child, report, write)

    items_dir = folder / "items"
    if storage.exists(items_dir) and storage.is_dir(items_dir):
        for child in storage.list_dir(items_dir):
            if child.name.endswith(".meta.json"):
                _ingest_item(storage, child, pueblo, report, write)


def _ingest_item(
    storage: StorageAdapter,
    meta_path: PurePosixPath,
    pueblo: Pueblo,
    report: IndexReport,
    write: sqlite3.Connection | None,
) -> None:
    try:
        data = _load_json(storage, meta_path)
        item = Item.model_validate(data)
    except (ValidationError, json.JSONDecodeError) as e:
        report.errors.append(f"{meta_path}: {e}")
        return

    # Si geo_id no estaba en el JSON, asumimos el pueblo de la carpeta como
    # origen geográfico. Mantiene retrocompatibilidad con items sin geo_id
    # explícito.
    if item.geo_id is None:
        item = item.model_copy(update={"geo_id": pueblo.id})

    if item.kind != ItemKind.url and item.file:
        # Verificar que el binario referenciado existe junto al .meta.json
        bin_path = meta_path.parent / item.file
        if not storage.exists(bin_path):
            report.errors.append(f"{meta_path}: fichero {item.file} no encontrado")
            return

    report.items += 1
    if write is not None:
        write.execute(
            "INSERT INTO item("
            "  id, kind, title, file, url, geo_id, song_id, sha256, mime_type, duration_s,"
            "  source_type, enrichment_status, has_external, platform, interpretes, tags,"
            "  segment_offset_s, segment_duration_s, raw_json, created_at, updated_at, fs_path"
            ") VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                str(item.id),
                item.kind.value,
                item.title,
                item.file,
                str(item.url) if item.url else None,
                str(item.geo_id) if item.geo_id else None,
                str(item.song_id) if item.song_id else None,
                item.sha256,
                item.mime_type,
                item.duration_s,
                item.source.type.value,
                item.enrichment.status.value,
                1 if item.external_metadata else 0,
                _platform(item),
                _interpretes_text(item),
                json.dumps(item.tags, ensure_ascii=False),
                item.segment.offset_s if item.segment else None,
                item.segment.duration_s if item.segment else None,
                item.model_dump_json(),
                item.created_at.isoformat(),
                item.updated_at.isoformat() if item.updated_at else None,
                str(meta_path),
            ),
        )


def _ingest_song(
    storage: StorageAdapter,
    meta_path: PurePosixPath,
    report: IndexReport,
    write: sqlite3.Connection | None,
) -> None:
    try:
        song = Song.model_validate(_load_json(storage, meta_path))
    except (ValidationError, json.JSONDecodeError) as e:
        report.errors.append(f"{meta_path}: {e}")
        return

    report.songs += 1
    report.relations += len(song.relations)
    if write is not None:
        write.execute(
            "INSERT INTO song(id, title, geo_id, title_variants, tags, notes, fs_path) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (
                str(song.id),
                song.title,
                str(song.geo_id) if song.geo_id else None,
                json.dumps(song.title_variants, ensure_ascii=False),
                json.dumps(song.tags, ensure_ascii=False),
                song.notes,
                str(meta_path),
            ),
        )
        for rel in song.relations:
            write.execute(
                "INSERT INTO relation(song_id, type, src_item, tgt_item, notes) "
                "VALUES (?, ?, ?, ?, ?)",
                (
                    str(song.id),
                    rel.type.value,
                    str(rel.source),
                    str(rel.target),
                    rel.notes,
                ),
            )
