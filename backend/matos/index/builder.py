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
    Disco,
    DiscoTrack,
    Huerfanas,
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
    huerfanas: int = 0
    items: int = 0
    songs: int = 0
    relations: int = 0
    discos: int = 0
    disco_tracks: int = 0
    track_segments: int = 0
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
        ("huerfanas_count", str(report.huerfanas)),
        ("items_count", str(report.items)),
        ("songs_count", str(report.songs)),
        ("relations_count", str(report.relations)),
        ("discos_count", str(report.discos)),
        ("disco_tracks_count", str(report.disco_tracks)),
        ("track_segments_count", str(report.track_segments)),
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


HUERFANAS_DIR = "_huerfanas"


def _walk(
    storage: StorageAdapter,
    report: IndexReport,
    write: sqlite3.Connection | None,
) -> None:
    # _index.json (opcional, pero recomendado)
    idx_path = PurePosixPath("_index.json")
    if storage.exists(idx_path):
        try:
            report.archive_meta = ArchiveIndex.model_validate(_load_json(storage, idx_path))
        except (ValidationError, json.JSONDecodeError) as e:
            report.errors.append(f"_index.json: {e}")

    # ── geo/ ────────────────────────────────────────────────────────────────
    geo_root = PurePosixPath("geo")
    if storage.exists(geo_root) and storage.is_dir(geo_root):
        _walk_geo(storage, geo_root, report, write)

    # ── discos/ ─────────────────────────────────────────────────────────────
    discos_root = PurePosixPath("discos")
    if storage.exists(discos_root) and storage.is_dir(discos_root):
        _walk_discos(storage, discos_root, report, write)


def _walk_geo(
    storage: StorageAdapter,
    geo_root: PurePosixPath,
    report: IndexReport,
    write: sqlite3.Connection | None,
) -> None:
    # _huerfanas/ a nivel raíz (sin CCAA conocida)
    root_huerfanas_dir = geo_root / HUERFANAS_DIR
    if storage.exists(root_huerfanas_dir) and storage.is_dir(root_huerfanas_dir):
        _ingest_huerfanas(storage, root_huerfanas_dir, parent=None, report=report, write=write)

    for ccaa_dir in storage.list_dir(geo_root):
        if not storage.is_dir(ccaa_dir) or ccaa_dir.name.startswith((".", "_")):
            continue
        ccaa = _ingest_ccaa(storage, ccaa_dir, report, write)
        if ccaa is None:
            continue

        # _huerfanas/ dentro de la CCAA (CCAA conocida, sin provincia)
        ccaa_huerfanas_dir = ccaa_dir / HUERFANAS_DIR
        if storage.exists(ccaa_huerfanas_dir) and storage.is_dir(ccaa_huerfanas_dir):
            _ingest_huerfanas(storage, ccaa_huerfanas_dir, parent=ccaa, report=report, write=write)

        for prov_dir in storage.list_dir(ccaa_dir):
            if not storage.is_dir(prov_dir) or prov_dir.name.startswith((".", "_")):
                continue
            prov = _ingest_provincia(storage, prov_dir, ccaa, report, write)
            if prov is None:
                continue

            # _huerfanas/ dentro de la provincia (provincia conocida, sin pueblo)
            prov_huerfanas_dir = prov_dir / HUERFANAS_DIR
            if storage.exists(prov_huerfanas_dir) and storage.is_dir(prov_huerfanas_dir):
                _ingest_huerfanas(
                    storage, prov_huerfanas_dir, parent=prov, report=report, write=write
                )

            for pueblo_dir in storage.list_dir(prov_dir):
                if not storage.is_dir(pueblo_dir) or pueblo_dir.name.startswith((".", "_")):
                    continue
                _ingest_pueblo(storage, pueblo_dir, prov, report, write)


def _walk_discos(
    storage: StorageAdapter,
    discos_root: PurePosixPath,
    report: IndexReport,
    write: sqlite3.Connection | None,
) -> None:
    # discos/<artista>/<(YYYY) titulo>/...
    for artista_dir in storage.list_dir(discos_root):
        if not storage.is_dir(artista_dir) or artista_dir.name.startswith((".", "_")):
            continue
        for disco_dir in storage.list_dir(artista_dir):
            if not storage.is_dir(disco_dir) or disco_dir.name.startswith((".", "_")):
                continue
            _ingest_disco(storage, disco_dir, report, write)


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

    _ingest_songs_and_items(storage, folder, default_geo_id=pueblo.id, report=report, write=write)


def _ingest_huerfanas(
    storage: StorageAdapter,
    folder: PurePosixPath,
    parent: CCAA | Provincia | None,
    report: IndexReport,
    write: sqlite3.Connection | None,
) -> None:
    """Bucket de songs/items con geo parcialmente conocida.

    Acepta `_huerfanas.json` opcional para fijar UUID estable; si falta, se
    sintetiza un UUID derivado del path (estable entre reindex)."""
    meta = folder / "_huerfanas.json"
    if storage.exists(meta):
        try:
            huerfanas = Huerfanas.model_validate(_load_json(storage, meta))
        except (ValidationError, json.JSONDecodeError) as e:
            report.errors.append(f"{meta}: {e}")
            return
    else:
        # UUID estable derivado del path → reindex idempotente
        from uuid import NAMESPACE_URL, UUID, uuid5

        synth_id: UUID = uuid5(NAMESPACE_URL, f"matos:huerfanas:{folder}")
        nombre_default = (
            f"Huérfanas ({parent.nombre})" if parent is not None else "Huérfanas (sin CCAA)"
        )
        huerfanas = Huerfanas(id=synth_id, nombre=nombre_default)

    report.huerfanas += 1

    # path: cadena de slugs hasta este folder, sin el segmento `geo/`.
    parts: list[str] = []
    cur = folder
    while cur.name and cur.name != "geo":
        parts.insert(0, cur.name)
        cur = cur.parent
    path = _path_dotted(parts)

    if write is not None:
        write.execute(
            "INSERT INTO geo_unit(id, level, nombre, parent_id, path, slug, codigo, fs_path, extra_json) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                str(huerfanas.id),
                huerfanas.level.value,
                huerfanas.nombre,
                str(parent.id) if parent is not None else None,
                path,
                _slug(folder),
                None,
                str(folder),
                json.dumps({"notas": huerfanas.notas}, ensure_ascii=False),
            ),
        )

    _ingest_songs_and_items(
        storage, folder, default_geo_id=huerfanas.id, report=report, write=write
    )


def _ingest_songs_and_items(
    storage: StorageAdapter,
    folder: PurePosixPath,
    default_geo_id,  # UUID
    report: IndexReport,
    write: sqlite3.Connection | None,
) -> None:
    """Lógica compartida pueblo/huerfanas: indexar `songs/` e `items/`.

    Songs antes que items: `item.song_id` tiene FK contra `song(id)` y la
    FK se valida en cada INSERT.
    """
    songs_dir = folder / "songs"
    if storage.exists(songs_dir) and storage.is_dir(songs_dir):
        for child in storage.list_dir(songs_dir):
            if child.name.endswith(".song.json"):
                _ingest_song(storage, child, report, write)

    items_dir = folder / "items"
    if storage.exists(items_dir) and storage.is_dir(items_dir):
        for child in storage.list_dir(items_dir):
            if child.name.endswith(".meta.json"):
                _ingest_item_with_default_geo(storage, child, default_geo_id, report, write)


def _ingest_item_with_default_geo(
    storage: StorageAdapter,
    meta_path: PurePosixPath,
    default_geo_id,  # UUID
    report: IndexReport,
    write: sqlite3.Connection | None,
) -> None:
    try:
        data = _load_json(storage, meta_path)
        item = Item.model_validate(data)
    except (ValidationError, json.JSONDecodeError) as e:
        report.errors.append(f"{meta_path}: {e}")
        return

    # Si geo_id no estaba en el JSON, asumimos la geo_unit de la carpeta
    # (pueblo o huerfanas) como origen geográfico. Mantiene retrocompatibilidad
    # con items sin geo_id explícito.
    if item.geo_id is None:
        item = item.model_copy(update={"geo_id": default_geo_id})

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
            "INSERT INTO song(id, title, geo_id, title_variants, tags, notes, "
            "original_recording_missing, fs_path) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (
                str(song.id),
                song.title,
                str(song.geo_id) if song.geo_id else None,
                json.dumps(song.title_variants, ensure_ascii=False),
                json.dumps(song.tags, ensure_ascii=False),
                song.notes,
                1 if song.original_recording_missing else 0,
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


# ─── Discos ────────────────────────────────────────────────────────────────


def _ingest_disco(
    storage: StorageAdapter,
    folder: PurePosixPath,
    report: IndexReport,
    write: sqlite3.Connection | None,
) -> None:
    """Ingesta un disco: `_disco.json` + tracks en `metadatos/*.track.json`.

    Cada track referencia un binario en la carpeta del disco; la existencia
    del binario se valida igual que en `_ingest_item`.
    """
    meta = folder / "_disco.json"
    if not storage.exists(meta):
        report.errors.append(f"{folder}: falta _disco.json")
        return
    try:
        disco = Disco.model_validate(_load_json(storage, meta))
    except (ValidationError, json.JSONDecodeError) as e:
        report.errors.append(f"{meta}: {e}")
        return

    if disco.cover_file is not None and not storage.exists(folder / disco.cover_file):
        report.errors.append(f"{meta}: cover_file {disco.cover_file} no encontrado")
        return

    report.discos += 1
    if write is not None:
        write.execute(
            "INSERT INTO disco("
            "  id, artista, titulo, año, sello, catalogo, formato, cover_file,"
            "  enrichment_status, has_external, notas, tags, raw_json, fs_path"
            ") VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                str(disco.id),
                disco.artista,
                disco.titulo,
                disco.año,
                disco.sello,
                disco.catalogo,
                disco.formato.value if disco.formato else None,
                disco.cover_file,
                disco.enrichment.status.value,
                1 if disco.external_metadata else 0,
                disco.notas,
                json.dumps(disco.tags, ensure_ascii=False),
                disco.model_dump_json(),
                str(meta),
            ),
        )

    metadatos_dir = folder / "metadatos"
    if not (storage.exists(metadatos_dir) and storage.is_dir(metadatos_dir)):
        return

    seen_track_nos: set[int] = set()
    for child in storage.list_dir(metadatos_dir):
        if not child.name.endswith(".track.json"):
            continue
        _ingest_disco_track(storage, child, disco, folder, seen_track_nos, report, write)


def _ingest_disco_track(
    storage: StorageAdapter,
    meta_path: PurePosixPath,
    disco: Disco,
    disco_folder: PurePosixPath,
    seen_track_nos: set[int],
    report: IndexReport,
    write: sqlite3.Connection | None,
) -> None:
    try:
        track = DiscoTrack.model_validate(_load_json(storage, meta_path))
    except (ValidationError, json.JSONDecodeError) as e:
        report.errors.append(f"{meta_path}: {e}")
        return

    if track.disco_id != disco.id:
        report.errors.append(f"{meta_path}: disco_id={track.disco_id} no coincide con {disco.id}")
        return

    if track.track_no in seen_track_nos:
        report.errors.append(f"{meta_path}: track_no={track.track_no} duplicado en disco")
        return
    seen_track_nos.add(track.track_no)

    bin_path = disco_folder / track.file
    if not storage.exists(bin_path):
        report.errors.append(f"{meta_path}: fichero {track.file} no encontrado")
        return

    report.disco_tracks += 1
    if write is not None:
        write.execute(
            "INSERT INTO disco_track("
            "  id, disco_id, track_no, title, title_external, file, sha256,"
            "  duration_s, mime_type, notas, tags, raw_json, fs_path"
            ") VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                str(track.id),
                str(track.disco_id),
                track.track_no,
                track.title,
                track.title_external,
                track.file,
                track.sha256,
                track.duration_s,
                track.mime_type,
                track.notes,
                json.dumps(track.tags, ensure_ascii=False),
                track.model_dump_json(),
                str(meta_path),
            ),
        )

    for seg in track.segments:
        report.track_segments += 1
        if write is not None:
            # FK contra song(id) sólo si el song_id está poblado y existe en
            # la tabla. En modo estricto, el INSERT fallará si referencia un
            # song inexistente; lo capturamos como error de validación.
            if seg.song_id is not None:
                exists = write.execute(
                    "SELECT 1 FROM song WHERE id = ?", (str(seg.song_id),)
                ).fetchone()
                if exists is None:
                    report.errors.append(
                        f"{meta_path}: segmento {seg.id} referencia song_id={seg.song_id} "
                        f"no existente"
                    )
                    continue
            write.execute(
                "INSERT INTO track_segment("
                "  id, track_id, song_id, offset_s, duration_s, label, unmatched, notes"
                ") VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    str(seg.id),
                    str(track.id),
                    str(seg.song_id) if seg.song_id else None,
                    seg.offset_s,
                    seg.duration_s,
                    seg.label,
                    1 if seg.unmatched else 0,
                    seg.notes,
                ),
            )
