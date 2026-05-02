"""Modelo Song — entidad lógica que agrupa items relacionados.

Un Song es una canción canónica del archivo: "Romance de la Loba", "Jota
ladeada de Lubián", "Charrada de las velas". Distintas grabaciones, letras,
partituras y URLs apuntan al mismo Song vía `Item.song_id`.

`Song.relations` declara relaciones explícitas entre items que pertenecen al
mismo Song (la letra X corresponde a la grabación Y, la partitura Z transcribe
la grabación Y, etc.).
"""

from __future__ import annotations

from enum import StrEnum
from uuid import UUID

from pydantic import Field, model_validator

from .common import MatosModel


class RelationType(StrEnum):
    version_of = "version_of"
    """`source` es una versión/interpretación distinta de `target`."""

    lyrics_of = "lyrics_of"
    """`source` (item lyrics) contiene la letra de `target` (grabación)."""

    score_of = "score_of"
    """`source` (item score) es la partitura de `target` (grabación)."""

    cover_of = "cover_of"
    """`source` versiona a `target` (cover comercial)."""

    derived_from = "derived_from"
    """`source` se deriva técnicamente de `target` (remix, transcripción)."""

    same_as = "same_as"
    """`source` y `target` son la misma grabación en distintas plataformas."""


class Relation(MatosModel):
    """Arista dirigida entre dos items dentro de un Song.

    Usamos `source` y `target` (no `from`/`to`) para evitar colisión con la
    palabra reservada `from` de Python al deserializar JSON.
    """

    type: RelationType
    source: UUID
    target: UUID
    notes: str | None = None

    @model_validator(mode="after")
    def _check_no_self_loop(self) -> Relation:
        if self.source == self.target:
            raise ValueError("Relation source and target must differ")
        return self


class Song(MatosModel):
    id: UUID
    title: str = Field(min_length=1)
    """Título canónico, legible. Variantes en `title_variants`."""

    title_variants: list[str] = Field(default_factory=list)
    """Otros títulos por los que se conoce esta canción."""

    geo_id: UUID | None = None
    """Origen geográfico canónico de la canción (no de cada grabación)."""

    items: list[UUID] = Field(default_factory=list)
    """IDs de items que pertenecen a esta canción.

    Redundante con `Item.song_id` pero útil como índice rápido al cargar
    el Song. La fuente de verdad es `Item.song_id`; en `make reindex` se
    reconcilian."""

    relations: list[Relation] = Field(default_factory=list)

    original_recording_missing: bool = False
    """`True` si la Song existe sólo como referencia desde uno o más discos
    pero no se ha localizado grabación de campo en el archivo. Útil para
    distinguir stubs creados desde un `TrackSegment` de canciones con
    grabaciones propias."""

    notes: str | None = None
    tags: list[str] = Field(default_factory=list)
