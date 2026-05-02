"""Pydantic v2 models — fuente de verdad de los schemas del archivo."""

from __future__ import annotations

from .common import SCHEMA_VERSION, MatosModel
from .disco import Disco, DiscoFormato, DiscoTrack, TrackSegment
from .geo import (
    CCAA,
    Centroid,
    ComarcaInfo,
    ComarcaTipo,
    GeoLevel,
    Huerfanas,
    Provincia,
    Pueblo,
)
from .index import ArchiveIndex
from .item import (
    BroadcastInfo,
    EnrichmentInfo,
    EnrichmentStatus,
    ExternalMetadata,
    ExternalSource,
    Item,
    ItemContext,
    ItemKind,
    ItemSource,
    Lugar,
    Platform,
    ReleaseInfo,
    Rights,
    Segment,
    SourceType,
)
from .song import Relation, RelationType, Song

__all__ = [
    # common
    "SCHEMA_VERSION",
    "MatosModel",
    # geo
    "CCAA",
    "Centroid",
    "ComarcaInfo",
    "ComarcaTipo",
    "GeoLevel",
    "Huerfanas",
    "Provincia",
    "Pueblo",
    # item
    "BroadcastInfo",
    "EnrichmentInfo",
    "EnrichmentStatus",
    "ExternalMetadata",
    "ExternalSource",
    "Item",
    "ItemContext",
    "ItemKind",
    "ItemSource",
    "Lugar",
    "Platform",
    "ReleaseInfo",
    "Rights",
    "Segment",
    "SourceType",
    # song
    "Relation",
    "RelationType",
    "Song",
    # disco
    "Disco",
    "DiscoFormato",
    "DiscoTrack",
    "TrackSegment",
    # index
    "ArchiveIndex",
]
