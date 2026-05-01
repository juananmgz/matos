"""Tests end-to-end del builder del índice SQLite.

Construye un archivo de juguete en `tmp_path` con CCAA → Provincia → Pueblo,
items y songs, y verifica:
- la validación pura (no escribe SQLite),
- el rebuild completo del índice,
- las consultas básicas (`get_item`, `tree`, `items_of_geo`, FTS),
- el comportamiento ante JSON inválido (no se escribe el destino).
"""

from __future__ import annotations

import json
import sqlite3
from datetime import UTC, datetime
from pathlib import Path
from uuid import UUID, uuid4

import pytest

from matos.index import build_index, validate_archive
from matos.index.queries import (
    connect,
    get_item,
    get_meta,
    get_song,
    items_of_geo,
    items_of_song,
    list_ccaa,
    list_children,
    search_items,
    tree,
)
from matos.models import (
    CCAA,
    SCHEMA_VERSION,
    ArchiveIndex,
    EnrichmentInfo,
    EnrichmentStatus,
    Item,
    ItemContext,
    ItemKind,
    ItemSource,
    Provincia,
    Pueblo,
    Relation,
    RelationType,
    ReleaseInfo,
    Rights,
    Song,
    SourceType,
)
from matos.models.item import Platform
from matos.storage import LocalStorage


def _now() -> datetime:
    return datetime.now(UTC)


def _dump(model, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        model.model_dump_json(indent=2, exclude_none=True) + "\n",
        encoding="utf-8",
    )


# ─── fixture: archivo de juguete ─────────────────────────────────────────


@pytest.fixture
def sample_archive(tmp_path: Path) -> tuple[Path, dict[str, UUID]]:
    """Crea archivo/ con: Andalucía/Granada/Pampaneira (1 audio + 1 song
    con 2 items + 1 relación) y CCAA "_dot" que debe ignorarse."""
    root = tmp_path / "archivo"
    ids: dict[str, UUID] = {
        "ccaa": uuid4(),
        "prov": uuid4(),
        "pueblo": uuid4(),
        "audio": uuid4(),
        "lyrics": uuid4(),
        "song": uuid4(),
    }

    _dump(
        ArchiveIndex(schema_version=SCHEMA_VERSION, archive_name="Test"),
        root / "_index.json",
    )

    # Carpeta oculta con `_` — debe ignorarse en walk
    (root / "_drafts").mkdir(parents=True)

    _dump(
        CCAA(id=ids["ccaa"], nombre="Andalucía", codigo="01"),
        root / "andalucia" / "_ccaa.json",
    )
    _dump(
        Provincia(id=ids["prov"], nombre="Granada", codigo_ine="18"),
        root / "andalucia" / "granada" / "_provincia.json",
    )
    _dump(
        Pueblo(id=ids["pueblo"], nombre="Pampaneira", codigo_ine="18142"),
        root / "andalucia" / "granada" / "pampaneira" / "_pueblo.json",
    )

    items_dir = root / "andalucia" / "granada" / "pampaneira" / "items"
    songs_dir = root / "andalucia" / "granada" / "pampaneira" / "songs"

    # audio + binario al lado
    audio_file = "romance.flac"
    (items_dir).mkdir(parents=True, exist_ok=True)
    (items_dir / audio_file).write_bytes(b"FLAC-FAKE-PAYLOAD")
    audio = Item(
        id=ids["audio"],
        kind=ItemKind.audio,
        title="Romance de la Loba",
        file=audio_file,
        geo_id=ids["pueblo"],
        song_id=ids["song"],
        context=ItemContext(interprete=["María"], recopilador=["Pérez"]),
        source=ItemSource(type=SourceType.fieldwork),
        rights=Rights(license="CC-BY-4.0"),
        enrichment=EnrichmentInfo(status=EnrichmentStatus.complete),
        tags=["romance", "loba"],
        created_at=_now(),
    )
    _dump(audio, items_dir / f"{audio.id}.meta.json")

    # lyrics como item URL (sin fichero)
    lyrics = Item(
        id=ids["lyrics"],
        kind=ItemKind.url,
        title="Letra Romance de la Loba",
        url="https://example.com/letra.txt",
        geo_id=ids["pueblo"],
        song_id=ids["song"],
        source=ItemSource(
            type=SourceType.release,
            release=ReleaseInfo(platform=Platform.other, artist="Anónimo"),
        ),
        rights=Rights(license="CC0-1.0"),
        created_at=_now(),
    )
    _dump(lyrics, items_dir / f"{lyrics.id}.meta.json")

    song = Song(
        id=ids["song"],
        title="Romance de la Loba",
        title_variants=["La Loba Parda"],
        items=[ids["audio"], ids["lyrics"]],
        relations=[
            Relation(type=RelationType.lyrics_of, source=ids["lyrics"], target=ids["audio"]),
        ],
        tags=["romance"],
    )
    _dump(song, songs_dir / f"{song.id}.song.json")

    return root, ids


# ─── tests ───────────────────────────────────────────────────────────────


class TestValidate:
    def test_valid_archive_no_errors(self, sample_archive: tuple[Path, dict]) -> None:
        root, _ = sample_archive
        report = validate_archive(LocalStorage(root))
        assert report.ok, report.errors
        assert report.ccaa == 1
        assert report.provincias == 1
        assert report.pueblos == 1
        assert report.items == 2
        assert report.songs == 1
        assert report.relations == 1

    def test_invalid_json_reported(self, sample_archive: tuple[Path, dict]) -> None:
        root, _ = sample_archive
        # Corromper el _ccaa.json
        (root / "andalucia" / "_ccaa.json").write_text("{not json", encoding="utf-8")
        report = validate_archive(LocalStorage(root))
        assert not report.ok
        assert any("_ccaa.json" in e for e in report.errors)

    def test_missing_binary_reported(self, sample_archive: tuple[Path, dict]) -> None:
        root, ids = sample_archive
        items_dir = root / "andalucia" / "granada" / "pampaneira" / "items"
        # Borrar el FLAC referenciado
        (items_dir / "romance.flac").unlink()
        report = validate_archive(LocalStorage(root))
        assert not report.ok
        assert any("no encontrado" in e for e in report.errors)
        _ = ids

    def test_underscore_folders_ignored(self, sample_archive: tuple[Path, dict]) -> None:
        # Carpeta `_drafts` no debería aparecer ni causar errores
        root, _ = sample_archive
        report = validate_archive(LocalStorage(root))
        assert report.ok


class TestBuild:
    def test_full_rebuild(self, sample_archive: tuple[Path, dict], tmp_path: Path) -> None:
        root, ids = sample_archive
        db = tmp_path / "matos.db"
        report = build_index(LocalStorage(root), db)
        assert report.ok, report.errors
        assert db.exists()

        with connect(db) as c:
            ccaa = list_ccaa(c)
            assert len(ccaa) == 1
            assert ccaa[0]["nombre"] == "Andalucía"
            provincias = list_children(c, str(ids["ccaa"]))
            assert len(provincias) == 1
            assert provincias[0]["nombre"] == "Granada"
            pueblos = list_children(c, str(ids["prov"]))
            assert len(pueblos) == 1
            assert pueblos[0]["path"] == "andalucia.granada.pampaneira"

            items = items_of_geo(c, str(ids["pueblo"]))
            assert len(items) == 2
            audio = get_item(c, str(ids["audio"]))
            assert audio is not None
            assert audio["kind"] == "audio"
            assert audio["raw"]["title"] == "Romance de la Loba"

            song = get_song(c, str(ids["song"]))
            assert song is not None
            assert len(song["relations"]) == 1
            assert song["relations"][0]["type"] == "lyrics_of"

            song_items = items_of_song(c, str(ids["song"]))
            assert {it["kind"] for it in song_items} == {"audio", "url"}

            meta = get_meta(c)
            assert meta["schema_version"] == SCHEMA_VERSION
            assert meta["items_count"] == "2"

    def test_fts_search(self, sample_archive: tuple[Path, dict], tmp_path: Path) -> None:
        root, _ = sample_archive
        db = tmp_path / "matos.db"
        build_index(LocalStorage(root), db)

        with connect(db) as c:
            hits = search_items(c, "loba")
            assert len(hits) >= 1
            # diacríticos: "Maria" (sin tilde) debe encontrar "María"
            hits = search_items(c, "Maria")
            assert any("María" in h["raw"]["context"]["interprete"][0] for h in hits)

    def test_tree_nested(self, sample_archive: tuple[Path, dict], tmp_path: Path) -> None:
        root, _ = sample_archive
        db = tmp_path / "matos.db"
        build_index(LocalStorage(root), db)
        with connect(db) as c:
            t = tree(c)
            assert len(t) == 1
            assert t[0]["level"] == "ccaa"
            assert len(t[0]["children"]) == 1
            assert t[0]["children"][0]["level"] == "provincia"
            assert t[0]["children"][0]["children"][0]["level"] == "pueblo"

    def test_invalid_archive_does_not_overwrite(
        self, sample_archive: tuple[Path, dict], tmp_path: Path
    ) -> None:
        root, _ = sample_archive
        db = tmp_path / "matos.db"
        # Build válido inicial
        build_index(LocalStorage(root), db)
        original = db.read_bytes()

        # Romper el archivo y rebuild — no debe sobrescribir el destino válido
        (root / "andalucia" / "_ccaa.json").write_text("{not json", encoding="utf-8")
        report = build_index(LocalStorage(root), db)
        assert not report.ok
        assert db.read_bytes() == original  # intacto
        assert not (db.with_suffix(db.suffix + ".tmp")).exists()  # tmp limpiado


class TestQueriesReadOnly:
    def test_connect_read_only_rejects_writes(
        self, sample_archive: tuple[Path, dict], tmp_path: Path
    ) -> None:
        root, _ = sample_archive
        db = tmp_path / "matos.db"
        build_index(LocalStorage(root), db)
        with connect(db) as c, pytest.raises(sqlite3.OperationalError):
            c.execute("INSERT INTO meta(key, value) VALUES ('x', 'y')")


class TestIngestDefaults:
    def test_geo_id_defaults_to_pueblo(
        self, sample_archive: tuple[Path, dict], tmp_path: Path
    ) -> None:
        """Item sin `geo_id` toma el del pueblo de su carpeta."""
        root, ids = sample_archive
        items_dir = root / "andalucia" / "granada" / "pampaneira" / "items"
        # Reescribir el item lyrics sin geo_id
        path = items_dir / f"{ids['lyrics']}.meta.json"
        data = json.loads(path.read_text())
        data.pop("geo_id", None)
        path.write_text(json.dumps(data), encoding="utf-8")

        db = tmp_path / "matos.db"
        build_index(LocalStorage(root), db)
        with connect(db) as c:
            it = get_item(c, str(ids["lyrics"]))
            assert it is not None
            assert it["geo_id"] == str(ids["pueblo"])
