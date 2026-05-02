"""Modelos de discos: `Disco`, `DiscoTrack`, `TrackSegment`.

Un **Disco** es una edición discográfica (LP, CD, EP, single, álbum digital)
de un artista de folklore tradicional o folk moderno. Vive en
`archivo/discos/<artista>/<(YYYY) titulo>/`.

Cada fichero sonoro del disco es un **DiscoTrack**, descrito por un sidecar
`metadatos/<nombre>.track.json`. Un track contiene 1 o N **TrackSegment**s:
cada segmento mapea un tramo (`offset_s`, `duration_s` ambos opcionales) a
una `Song` del archivo geográfico.

Bidireccionalidad disco ↔ pueblo:

- Si la canción tradicional ya existe en `archivo/geo/<...>/songs/`, el
  segmento la referencia vía `song_id`. La consulta inversa (qué tracks
  contienen esta Song) se resuelve por SQL contra `track_segment`.
- Si NO existe grabación de campo, se crea un `Song` *stub* en el nivel
  geográfico más fino conocido (pueblo, o `_huerfanas/` del nivel
  correspondiente) con `original_recording_missing=true`. El segmento
  apunta a ese stub. El stub no tiene Items propios; sólo existe para
  representar la canción y permitir que aparezca en la navegación geográfica.
- Si no se conoce nada del origen, el stub vive en `archivo/geo/_huerfanas/`.

Mapeo MNEMOSINE futuro:
- `Disco` → tabla `release`.
- `DiscoTrack` → tabla `release_track`.
- `TrackSegment` → tabla `media_segment` con `work_id`.
"""

from __future__ import annotations

from enum import StrEnum
from typing import Annotated
from uuid import UUID

from pydantic import Field, model_validator

from .common import MatosModel
from .item import EnrichmentInfo, ExternalMetadata, Rights, Sha256Str


class DiscoFormato(StrEnum):
    lp = "lp"
    ep = "ep"
    single = "single"
    cd = "cd"
    casete = "casete"
    digital = "digital"
    otro = "otro"


class Disco(MatosModel):
    """Una edición discográfica concreta. Sidecar: `_disco.json`.

    Identidad por UUID. La carpeta puede renombrarse sin romper relaciones.
    """

    id: UUID
    artista: str = Field(min_length=1)
    titulo: str = Field(min_length=1)
    año: int | None = Field(default=None, ge=1850, le=2100)
    sello: str | None = None
    catalogo: str | None = None
    formato: DiscoFormato | None = None

    cover_file: str | None = None
    """Nombre del fichero de carátula relativo a la carpeta del disco."""

    notas: str | None = None
    tags: list[str] = Field(default_factory=list)

    rights: Rights
    external_metadata: ExternalMetadata | None = None
    enrichment: EnrichmentInfo = Field(default_factory=EnrichmentInfo)


class TrackSegment(MatosModel):
    """Tramo de un `DiscoTrack` que se identifica con una canción tradicional.

    `offset_s` / `duration_s` son opcionales:
    - Sin `offset_s` → el segmento empieza al inicio del track.
    - Sin `duration_s` → el segmento llega hasta el final del track.
    - Sin ninguno de los dos → el track entero es la canción.

    `song_id` puede ser `None` en dos casos:
    - El segmento aún no se ha mapeado a una Song concreta (en curación).
    - Se sabe que no existe Song en el archivo (`unmatched=true` lo declara
      explícitamente para distinguir de "sin curar").
    """

    id: UUID
    song_id: UUID | None = None
    offset_s: int | None = Field(default=None, ge=0)
    duration_s: int | None = Field(default=None, gt=0)
    label: str | None = None
    """Texto libre describiendo el tramo (ej. "tema A", "estribillo")."""

    unmatched: bool = False
    """`True` si se ha verificado que no hay Song equivalente en el archivo
    y no procede crearla todavía. Distinto de `song_id is None` por curar."""

    notes: str | None = None

    @model_validator(mode="after")
    def _check_unmatched_consistency(self) -> TrackSegment:
        if self.unmatched and self.song_id is not None:
            raise ValueError("unmatched=True requires song_id=None")
        return self


class DiscoTrack(MatosModel):
    """Un fichero sonoro del disco. Sidecar: `metadatos/<nombre>.track.json`.

    `file` es el nombre del binario relativo a la carpeta del disco
    (no a `metadatos/`). Esto permite mover los sidecars de carpeta sin
    romper la referencia y deja claro que el binario es hermano del
    `_disco.json`.
    """

    id: UUID
    disco_id: UUID
    track_no: Annotated[int, Field(ge=1)]
    title: str = Field(min_length=1)
    """Título canónico del archivo (verdad editable)."""

    title_external: str | None = None
    """Título tal y como aparece impreso en la edición o en la plataforma."""

    file: str = Field(min_length=1)
    """Nombre del binario relativo a la carpeta del disco."""

    sha256: Sha256Str | None = None
    duration_s: int | None = Field(default=None, ge=0)
    mime_type: str | None = None

    segments: list[TrackSegment] = Field(default_factory=list)
    notes: str | None = None
    tags: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def _check_segments_within_duration(self) -> DiscoTrack:
        if self.duration_s is None:
            return self
        for seg in self.segments:
            start = seg.offset_s or 0
            if seg.duration_s is not None and start + seg.duration_s > self.duration_s:
                raise ValueError(
                    f"segment {seg.id} excede duración del track "
                    f"({start + seg.duration_s}s > {self.duration_s}s)"
                )
        return self

    @model_validator(mode="after")
    def _check_unique_segment_ids(self) -> DiscoTrack:
        ids = [s.id for s in self.segments]
        if len(ids) != len(set(ids)):
            raise ValueError("segment ids must be unique within a track")
        return self
