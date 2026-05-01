"""Tests de los modelos Pydantic.

Cubre:
- Construcción mínima y completa de cada entidad.
- Invariantes (kind ↔ file/url, source.type ↔ release/broadcast, rangos).
- Caso real de uso: "Ringorrando — J#4" (verdad externa vs. archivo).
- Roundtrip JSON: model → dump → load → equals.
- `compute_status` del Item.
"""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest
from pydantic import ValidationError

from matos.models import (
    CCAA,
    ArchiveIndex,
    BroadcastInfo,
    Centroid,
    ComarcaInfo,
    ComarcaTipo,
    EnrichmentInfo,
    EnrichmentStatus,
    ExternalMetadata,
    ExternalSource,
    GeoLevel,
    Item,
    ItemContext,
    ItemKind,
    ItemSource,
    Lugar,
    Platform,
    Provincia,
    Pueblo,
    Relation,
    RelationType,
    ReleaseInfo,
    Rights,
    Segment,
    Song,
    SourceType,
)


def _sha256(s: str) -> str:
    return "sha256:" + hashlib.sha256(s.encode()).hexdigest()


def _now() -> datetime:
    return datetime.now(UTC)


# ─── Geo ──────────────────────────────────────────────────────────────────────


class TestGeo:
    def test_ccaa_minimal(self) -> None:
        c = CCAA(id=uuid4(), nombre="Andalucía")
        assert c.level == GeoLevel.ccaa
        assert c.codigo is None

    def test_provincia_codigo_ine_pattern(self) -> None:
        Provincia(id=uuid4(), nombre="Granada", codigo_ine="18")
        with pytest.raises(ValidationError):
            Provincia(id=uuid4(), nombre="Mal", codigo_ine="1")  # 1 dígito
        with pytest.raises(ValidationError):
            Provincia(id=uuid4(), nombre="Mal", codigo_ine="ABC")

    def test_pueblo_full(self) -> None:
        p = Pueblo(
            id=uuid4(),
            nombre="Pampaneira",
            codigo_ine="18142",
            comarca=ComarcaInfo(
                nombre="Alpujarra",
                tipo=ComarcaTipo.etnomusicologica,
                fuente="IGN",
            ),
            subcomarca=ComarcaInfo(nombre="Bajo Alpujarra", tipo=ComarcaTipo.manual),
            centroid=Centroid(lat=36.943, lon=-3.357),
        )
        assert p.codigo_ine == "18142"
        assert p.comarca is not None
        assert p.comarca.tipo == ComarcaTipo.etnomusicologica

    def test_pueblo_codigo_ine_must_be_5_digits(self) -> None:
        with pytest.raises(ValidationError):
            Pueblo(id=uuid4(), nombre="X", codigo_ine="123")

    def test_centroid_bounds(self) -> None:
        Centroid(lat=0, lon=0)
        Centroid(lat=90, lon=180)
        Centroid(lat=-90, lon=-180)
        with pytest.raises(ValidationError):
            Centroid(lat=91, lon=0)
        with pytest.raises(ValidationError):
            Centroid(lat=0, lon=181)


# ─── Item — invariantes ──────────────────────────────────────────────────────


class TestItemInvariants:
    def _base_args(self) -> dict:
        return {
            "id": uuid4(),
            "title": "X",
            "source": ItemSource(type=SourceType.fieldwork),
            "rights": Rights(license="CC-BY-4.0"),
            "created_at": _now(),
        }

    def test_audio_requires_file(self) -> None:
        with pytest.raises(ValidationError, match="requires `file`"):
            Item(kind=ItemKind.audio, **self._base_args())

    def test_audio_with_file_ok(self) -> None:
        Item(kind=ItemKind.audio, file="x.flac", **self._base_args())

    def test_url_requires_url(self) -> None:
        with pytest.raises(ValidationError, match="requires `url`"):
            Item(kind=ItemKind.url, **self._base_args())

    def test_url_cannot_have_file(self) -> None:
        with pytest.raises(ValidationError, match="cannot have `file`"):
            Item(
                kind=ItemKind.url,
                file="x.flac",
                url="https://example.com/x",
                **self._base_args(),
            )

    def test_release_requires_release_block(self) -> None:
        args = self._base_args()
        args["source"] = ItemSource(type=SourceType.release)
        with pytest.raises(ValidationError, match="requires `source.release`"):
            Item(kind=ItemKind.url, url="https://example.com/x", **args)

    def test_broadcast_requires_broadcast_block(self) -> None:
        args = self._base_args()
        args["source"] = ItemSource(type=SourceType.broadcast)
        with pytest.raises(ValidationError, match="requires `source.broadcast`"):
            Item(kind=ItemKind.url, url="https://example.com/x", **args)


class TestSegment:
    def test_valid(self) -> None:
        s = Segment(offset_s=145, duration_s=178, label="Jota 2")
        assert s.offset_s == 145

    def test_negative_offset_rejected(self) -> None:
        with pytest.raises(ValidationError):
            Segment(offset_s=-1, duration_s=10)

    def test_zero_duration_rejected(self) -> None:
        with pytest.raises(ValidationError):
            Segment(offset_s=0, duration_s=0)


# ─── Caso de uso: Ringorrando — J#4 ──────────────────────────────────────────


class TestRingorrandoCase:
    """Verdad externa (Spotify dice 'J#4') vs. verdad del archivo
    (es la jota ladeada de Lubián, recopilada por contraste con grabaciones
    de campo). Ambas conviven en el mismo Item."""

    def test_ringorrando_j4(self) -> None:
        spotify_url = "https://open.spotify.com/track/abc123def456"
        raw = {
            "name": "J#4",
            "artists": [{"name": "Ringorrando"}],
            "album": {"name": "..."},
        }

        item = Item(
            id=uuid4(),
            kind=ItemKind.url,
            title="Jota de los laos (Jota ladeada)",
            url=spotify_url,
            geo_id=uuid4(),
            song_id=uuid4(),
            context=ItemContext(
                interprete=["Ringorrando"],
                fecha="2023",
                lugar_origen="Lubián, Zamora",
            ),
            source=ItemSource(
                type=SourceType.release,
                release=ReleaseInfo(
                    platform=Platform.spotify,
                    track_id="abc123def456",
                    track_number=4,
                    track_title_external="J#4",
                    artist="Ringorrando",
                    release_year=2023,
                ),
            ),
            rights=Rights(license="all-rights-reserved", holder="Ringorrando"),
            external_metadata=ExternalMetadata(
                source=ExternalSource.spotify_api,
                fetched_at=_now(),
                url=spotify_url,
                raw=raw,
                raw_hash=_sha256(json.dumps(raw, sort_keys=True)),
            ),
            enrichment=EnrichmentInfo(
                status=EnrichmentStatus.complete,
                edited_by="juananmgz",
                edited_at=_now(),
                notes=(
                    "Ringorrando codifica títulos como J#1..J#N. Este es la "
                    "jota ladeada de Lubián; confirmado por contraste con "
                    "grabación de campo de 1985."
                ),
            ),
            tags=["jota", "jota ladeada", "ringorrando"],
            created_at=_now(),
        )

        # archivo > externo
        assert item.title == "Jota de los laos (Jota ladeada)"
        assert item.source.release is not None
        assert item.source.release.track_title_external == "J#4"

        # geo del item = origen, no ubicación del grupo
        assert item.context.lugar_origen == "Lubián, Zamora"

        # verdad externa preservada en raw
        assert item.external_metadata is not None
        assert item.external_metadata.raw["name"] == "J#4"

        # status complete porque title, geo_id, song_id están todos
        assert item.compute_status() == EnrichmentStatus.complete


# ─── compute_status ───────────────────────────────────────────────────────────


class TestComputeStatus:
    def _make(
        self,
        title: str = "?",
        geo_id: UUID | None = None,
        song_id: UUID | None = None,
        with_external: bool = False,
    ) -> Item:
        url = "https://example.com/track"
        ext = None
        if with_external:
            ext = ExternalMetadata(
                source=ExternalSource.spotify_api,
                fetched_at=_now(),
                url=url,
                raw={},
                raw_hash=_sha256("empty"),
            )
        return Item(
            id=uuid4(),
            kind=ItemKind.url,
            title=title,
            url=url,
            geo_id=geo_id,
            song_id=song_id,
            source=ItemSource(
                type=SourceType.release,
                release=ReleaseInfo(platform=Platform.spotify),
            ),
            rights=Rights(license="all-rights-reserved"),
            external_metadata=ext,
            created_at=_now(),
        )

    def test_pending_when_only_external(self) -> None:
        i = self._make(with_external=True)
        assert i.compute_status() == EnrichmentStatus.pending

    def test_partial_when_some_filled(self) -> None:
        i = self._make(title="Jota ladeada", geo_id=uuid4(), with_external=True)
        assert i.compute_status() == EnrichmentStatus.partial

    def test_complete_when_all_filled(self) -> None:
        i = self._make(title="Jota ladeada", geo_id=uuid4(), song_id=uuid4())
        assert i.compute_status() == EnrichmentStatus.complete


# ─── Song + Relation ─────────────────────────────────────────────────────────


class TestSong:
    def test_minimal(self) -> None:
        s = Song(id=uuid4(), title="Romance de la Loba")
        assert s.title == "Romance de la Loba"
        assert s.items == []

    def test_with_relations(self) -> None:
        a, b, c = uuid4(), uuid4(), uuid4()
        song = Song(
            id=uuid4(),
            title="Romance de la Loba",
            title_variants=["La Loba Parda"],
            items=[a, b, c],
            relations=[
                Relation(type=RelationType.lyrics_of, source=b, target=a),
                Relation(type=RelationType.score_of, source=c, target=a),
            ],
        )
        assert len(song.relations) == 2
        assert song.relations[0].type == RelationType.lyrics_of

    def test_relation_self_loop_rejected(self) -> None:
        x = uuid4()
        with pytest.raises(ValidationError):
            Relation(type=RelationType.version_of, source=x, target=x)


# ─── ArchiveIndex ────────────────────────────────────────────────────────────


class TestArchiveIndex:
    def test_minimal(self) -> None:
        idx = ArchiveIndex(schema_version="1.0.0")
        assert idx.schema_version == "1.0.0"

    def test_invalid_semver(self) -> None:
        with pytest.raises(ValidationError):
            ArchiveIndex(schema_version="1.0")


# ─── Roundtrip JSON ──────────────────────────────────────────────────────────


class TestJsonRoundtrip:
    """model → JSON string → parsed dict → model. Garantiza persistencia."""

    def test_pueblo(self) -> None:
        p = Pueblo(
            id=uuid4(),
            nombre="Lubián",
            codigo_ine="49120",
            comarca=ComarcaInfo(nombre="Sanabria", tipo=ComarcaTipo.funcional, fuente="MAPA"),
            centroid=Centroid(lat=42.045, lon=-6.857),
        )
        dumped = p.model_dump_json()
        loaded = Pueblo.model_validate_json(dumped)
        assert loaded == p

    def test_item_with_external(self) -> None:
        url = "https://www.youtube.com/watch?v=foo"
        item = Item(
            id=uuid4(),
            kind=ItemKind.url,
            title="Foo",
            url=url,
            source=ItemSource(
                type=SourceType.broadcast,
                broadcast=BroadcastInfo(platform=Platform.youtube, external_id="foo"),
            ),
            rights=Rights(license="CC-BY-4.0"),
            context=ItemContext(
                interprete=["Vecinos de X"],
                lugar_grabacion=Lugar(nombre="Plaza", lat=42.0, lon=-6.0),
            ),
            external_metadata=ExternalMetadata(
                source=ExternalSource.youtube_oembed,
                fetched_at=_now(),
                url=url,
                raw={"title": "Foo (oembed)"},
                raw_hash=_sha256("foo-raw"),
            ),
            tags=["test", "roundtrip"],
            created_at=_now(),
        )
        dumped = item.model_dump_json()
        loaded = Item.model_validate_json(dumped)
        assert loaded == item
        # verifica que las HttpUrl se serializan como string
        parsed = json.loads(dumped)
        assert isinstance(parsed["url"], str)
        assert parsed["url"].startswith("https://")

    def test_song(self) -> None:
        a, b = uuid4(), uuid4()
        song = Song(
            id=uuid4(),
            title="X",
            items=[a, b],
            relations=[Relation(type=RelationType.same_as, source=a, target=b)],
        )
        dumped = song.model_dump_json()
        loaded = Song.model_validate_json(dumped)
        assert loaded == song
