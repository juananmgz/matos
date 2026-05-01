"""Modelo Item — la unidad atómica del archivo.

Un Item representa **una** instancia concreta: una grabación de audio, un
vídeo, una partitura, una letra, o una URL externa que apunta a uno de los
anteriores en una plataforma (Spotify, YouTube, Wikimedia…).

Items se agrupan lógicamente en `Song` (canción canónica) vía `song_id`.

Dos capas de metadatos conviven:
- `external_metadata`: caché crudo de la plataforma. Solo se actualiza vía
  refetch; **nunca a mano**.
- Resto de campos top-level (`title`, `geo_id`, `context`, `source`, …):
  verdad del archivo, editada por el superusuario. **Nunca se sobrescribe
  por refetch**.
"""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Annotated, Any
from uuid import UUID

from pydantic import Field, HttpUrl, model_validator

from .common import MatosModel

# ─── Enums ────────────────────────────────────────────────────────────────────


class ItemKind(StrEnum):
    audio = "audio"
    video = "video"
    score = "score"  # partitura (PDF, MusicXML, imagen)
    lyrics = "lyrics"  # letra (texto)
    url = "url"  # solo URL, sin fichero local


class SourceType(StrEnum):
    """Origen del item.

    - `fieldwork`: grabación de campo (recopilación etnográfica).
    - `release`: edición comercial (disco, EP, single en plataforma).
    - `broadcast`: emisión radio/TV/internet.
    - `derived`: versión derivada (remix, transcripción, cover de cover).
    """

    fieldwork = "fieldwork"
    release = "release"
    broadcast = "broadcast"
    derived = "derived"


class Platform(StrEnum):
    spotify = "spotify"
    youtube = "youtube"
    apple_music = "apple_music"
    bandcamp = "bandcamp"
    soundcloud = "soundcloud"
    facebook = "facebook"
    wikimedia = "wikimedia"
    archive_org = "archive_org"
    other = "other"


class ExternalSource(StrEnum):
    """De qué API vino la `external_metadata.raw`."""

    spotify_api = "spotify_api"
    youtube_oembed = "youtube_oembed"
    youtube_data_api = "youtube_data_api"
    wikidata = "wikidata"
    wikimedia_commons = "wikimedia_commons"
    other = "other"


class EnrichmentStatus(StrEnum):
    pending = "pending"
    """Solo external_metadata, sin curación."""

    partial = "partial"
    """Curación parcial; faltan campos requeridos para `complete`."""

    complete = "complete"
    """Todos los campos requeridos rellenos."""

    needs_review = "needs_review"
    """external_metadata cambió desde la última edición; revisar diff."""


# ─── Estructuras anidadas ─────────────────────────────────────────────────────


class Lugar(MatosModel):
    """Ubicación de grabación/origen. Texto + opcionalmente coordenadas."""

    nombre: str | None = None
    lat: float | None = Field(default=None, ge=-90, le=90)
    lon: float | None = Field(default=None, ge=-180, le=180)


class ItemContext(MatosModel):
    """Contexto etnográfico — quién, cuándo, dónde."""

    interprete: list[str] = Field(default_factory=list)
    """Quién interpreta esta grabación concreta."""

    interprete_original: list[str] | None = None
    """Si esta versión deriva de otra, los intérpretes de la original."""

    recopilador: list[str] = Field(default_factory=list)
    """Quién recopiló (relevante en fieldwork)."""

    fecha: str | None = None
    """ISO 8601 parcial: "1973", "1973-08", o "1973-08-14"."""

    lugar_grabacion: Lugar | None = None
    lugar_origen: str | None = None
    """Texto libre del lugar de origen cultural (ej. "Lubián, Zamora").
    Cuando esté digitalizado, el `geo_id` del item apunta a la entidad
    correspondiente; este campo lo complementa cuando hace falta más detalle."""

    evento: str | None = None
    """Si la grabación es de un evento concreto (festividad, romería)."""


class ReleaseInfo(MatosModel):
    """Cuando `source.type == release`. Disco/EP/single en plataforma."""

    platform: Platform | None = None
    track_id: str | None = None
    track_number: int | None = Field(default=None, ge=1)
    track_title_external: str | None = None
    """Título tal-y-como-aparece-en-la-plataforma. Útil cuando el artista
    codifica títulos (caso "Ringorrando — J#4")."""

    album_title: str | None = None
    album_id: str | None = None
    artist: str | None = None
    label: str | None = None
    """Sello discográfico."""

    release_year: int | None = Field(default=None, ge=1850, le=2100)
    isrc: str | None = None


class BroadcastInfo(MatosModel):
    """Cuando `source.type == broadcast`."""

    platform: Platform | None = None
    program: str | None = None
    episode: str | None = None
    air_date: str | None = None  # ISO partial
    external_id: str | None = None


class ItemSource(MatosModel):
    type: SourceType
    release: ReleaseInfo | None = None
    broadcast: BroadcastInfo | None = None


class Rights(MatosModel):
    license: str
    """SPDX (`CC-BY-4.0`, `CC0-1.0`), `all-rights-reserved`, o texto libre."""

    holder: str | None = None
    """Titular de los derechos (artista, sello, recopilador, archivo)."""

    notes: str | None = None


class Segment(MatosModel):
    """Sub-sección de un media más largo.

    Cuando un track de Spotify o un vídeo de YouTube contiene varias canciones
    distintas (medley, álbum-track con varias jotas), se crea un Item por cada
    canción con la misma `url` y un `Segment` distinto.
    """

    offset_s: int = Field(ge=0)
    duration_s: int = Field(gt=0)
    label: str | None = None


class ExternalMetadata(MatosModel):
    """Caché crudo de la plataforma externa. Opaca, no validada por schema.

    Solo se actualiza con `POST /api/items/{id}/refetch`. **Nunca editar a
    mano**. `raw_hash` permite detectar cambios externos vs. la última
    versión vista durante la edición → triggers `needs_review`.
    """

    source: ExternalSource
    fetched_at: datetime
    url: HttpUrl
    raw: dict[str, Any]
    raw_hash: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")


class EnrichmentInfo(MatosModel):
    status: EnrichmentStatus = EnrichmentStatus.pending
    edited_by: str | None = None
    edited_at: datetime | None = None
    notes: str | None = None
    """Texto libre. Aquí va la lógica del enriquecimiento: códigos del
    artista, fuentes consultadas, contraste con otras grabaciones, etc."""


# ─── Item ─────────────────────────────────────────────────────────────────────


# Hash hex de 64 chars, prefijado con "sha256:".
Sha256Str = Annotated[str, Field(pattern=r"^sha256:[0-9a-f]{64}$")]


class Item(MatosModel):
    """Una unidad concreta del archivo: audio, vídeo, partitura, letra, o URL."""

    id: UUID
    kind: ItemKind
    title: str = Field(min_length=1)
    """Verdad del archivo. Sobrescribe el título externo de la plataforma."""

    file: str | None = None
    """Nombre del fichero (relativo a la carpeta `items/` del pueblo).
    Obligatorio si `kind != url`."""

    url: HttpUrl | None = None
    """URL externa. Obligatorio si `kind == url` o si el item se origina
    de una plataforma."""

    geo_id: UUID | None = None
    """Origen geográfico. NO es la ubicación del artista; es el origen
    cultural del repertorio (ej. Lubián para "J#4" de Ringorrando)."""

    song_id: UUID | None = None
    """Canción canónica que agrupa este item con otras versiones."""

    segment: Segment | None = None
    """Si este item es una sub-sección de un media más largo."""

    context: ItemContext = Field(default_factory=ItemContext)
    source: ItemSource
    rights: Rights

    external_metadata: ExternalMetadata | None = None
    enrichment: EnrichmentInfo = Field(default_factory=EnrichmentInfo)

    tags: list[str] = Field(default_factory=list)
    sha256: Sha256Str | None = None
    """Para items con fichero. Calculado por `matos new-item`."""

    mime_type: str | None = None
    duration_s: int | None = Field(default=None, ge=0)

    created_at: datetime
    updated_at: datetime | None = None

    # ── invariantes ──────────────────────────────────────────────────────────

    @model_validator(mode="after")
    def _check_kind_consistency(self) -> Item:
        if self.kind == ItemKind.url:
            if self.url is None:
                raise ValueError("kind=url requires `url` field")
            if self.file is not None:
                raise ValueError("kind=url cannot have `file` field")
        else:
            if self.file is None:
                raise ValueError(f"kind={self.kind.value} requires `file` field")
        return self

    @model_validator(mode="after")
    def _check_release_consistency(self) -> Item:
        if self.source.type == SourceType.release and self.source.release is None:
            raise ValueError("source.type=release requires `source.release`")
        if self.source.type == SourceType.broadcast and self.source.broadcast is None:
            raise ValueError("source.type=broadcast requires `source.broadcast`")
        return self

    # ── helpers ──────────────────────────────────────────────────────────────

    def compute_status(self) -> EnrichmentStatus:
        """Calcula el `EnrichmentStatus` que DEBERÍA tener este item dado su
        estado actual de campos. No detecta `needs_review` (eso requiere
        comparar con el `raw_hash` previo, que vive fuera del item)."""

        title_meaningful = self.title.strip() not in ("", "?", "Untitled", "—", "-")
        has_geo = self.geo_id is not None
        has_song = self.song_id is not None

        filled = sum([title_meaningful, has_geo, has_song])

        if filled == 3:
            return EnrichmentStatus.complete
        if filled == 0 and self.external_metadata is not None:
            return EnrichmentStatus.pending
        return EnrichmentStatus.partial
