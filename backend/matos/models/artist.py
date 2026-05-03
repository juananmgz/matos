"""Modelo `Artist`: artista (solista o grupo) referenciable desde `Disco`.

Sidecar: `archivo/artists/<slug>/_artist.json`. La carpeta `<slug>` coincide
con el campo `slug` y con el segmento de carpeta usado por los discos
(`archivo/discos/<slug>/...`), permitiendo resolver la FK `disco.artist_id`
por convención cuando no está declarada explícitamente.

`external_metadata` y `enrichment` siguen el mismo patrón que `Item` y
`Disco`: capa cruda de plataforma (Spotify/Discogs/Wikidata, futuro) +
estado de curación. Nunca se sobrescribe la verdad del archivo (`nombre`,
`aliases`, `bio`…) por refetch.

Mapeo MNEMOSINE futuro: tabla `artist` (entidad propia, no `release.artist`
free-text como ahora).
"""

from __future__ import annotations

from enum import StrEnum
from uuid import UUID

from pydantic import Field, HttpUrl

from .common import MatosModel
from .item import EnrichmentInfo, ExternalMetadata, Rights


class ArtistType(StrEnum):
    solo = "solo"
    grupo = "grupo"
    otro = "otro"


class Artist(MatosModel):
    """Un artista: solista, grupo, o entidad sin filiación clara.

    Identidad por UUID. El `slug` es único y debe ser ASCII (minúsculas,
    guiones); la carpeta del artista en disco coincide con él. Renombrar
    el slug requiere mover la carpeta y revalidar.
    """

    id: UUID
    nombre: str = Field(min_length=1)
    """Nombre legible (con acentos / mayúsculas / espacios)."""

    slug: str = Field(min_length=1, pattern=r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
    """Identificador estable derivado del nombre, ASCII kebab-case."""

    type: ArtistType | None = None
    geo_id: UUID | None = None
    """Origen geográfico del artista (no necesariamente coincide con la
    geo_unit de las canciones que interpreta)."""

    aliases: list[str] = Field(default_factory=list)
    bio: str | None = None
    links: list[HttpUrl] = Field(default_factory=list)
    """URLs externas: web oficial, Wikipedia, Wikidata, etc."""

    notas: str | None = None
    tags: list[str] = Field(default_factory=list)

    rights: Rights | None = None
    external_metadata: ExternalMetadata | None = None
    enrichment: EnrichmentInfo = Field(default_factory=EnrichmentInfo)
