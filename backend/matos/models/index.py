"""Modelo del fichero raíz `archivo/_index.json` — metadatos del archivo."""

from __future__ import annotations

from datetime import datetime

from pydantic import Field

from .common import MatosModel


class ArchiveIndex(MatosModel):
    """Metadatos generales del archivo. Vive en `archivo/_index.json`."""

    schema_version: str = Field(pattern=r"^\d+\.\d+\.\d+$")
    """SemVer del esquema de datos. Bump on breaking changes."""

    archive_name: str | None = None
    description: str | None = None
    maintainer: str | None = None

    created_at: datetime | None = None
    updated_at: datetime | None = None
