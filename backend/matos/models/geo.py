"""Modelos geográficos: CCAA → Provincia → Pueblo.

Filesystem layout:
    archivo/
        andalucia/
            _ccaa.json          → CCAA
            granada/
                _provincia.json → Provincia
                pampaneira/
                    _pueblo.json → Pueblo

Comarcas y subcomarcas son atributos de Pueblo (no nivel propio en filesystem)
por la complejidad legal/política del concepto en España (cf. doc arquitectura
sección 6).
"""

from __future__ import annotations

from enum import StrEnum
from typing import Literal
from uuid import UUID

from pydantic import Field

from .common import MatosModel


class GeoLevel(StrEnum):
    ccaa = "ccaa"
    provincia = "provincia"
    pueblo = "pueblo"


class ComarcaTipo(StrEnum):
    """Origen y validez de la delimitación. Crítico mostrarlo en UI."""

    legal = "legal"
    """Reconocida por ley autonómica (Cataluña, Aragón, El Bierzo, etc.)."""

    funcional = "funcional"
    """Sin rango legal pero documentada (INE/MAPA/IGN)."""

    etnomusicologica = "etnomusicologica"
    """Definida por el archivo según contexto cultural/musical."""

    manual = "manual"
    """Inserción manual del usuario, sin fuente formal."""


class Centroid(MatosModel):
    """Punto representativo (no centroide geométrico estricto)."""

    lat: float = Field(ge=-90, le=90)
    lon: float = Field(ge=-180, le=180)


class ComarcaInfo(MatosModel):
    nombre: str = Field(min_length=1)
    tipo: ComarcaTipo
    fuente: str | None = None
    """Procedencia de la delimitación (ej. "IGN", "ICGC", "tradición oral")."""


class _GeoBase(MatosModel):
    id: UUID
    nombre: str = Field(min_length=1)
    notas: str | None = None


class CCAA(_GeoBase):
    level: Literal[GeoLevel.ccaa] = GeoLevel.ccaa
    codigo: str | None = Field(default=None, description="Código CCAA INE (1-19).")


class Provincia(_GeoBase):
    level: Literal[GeoLevel.provincia] = GeoLevel.provincia
    codigo_ine: str | None = Field(default=None, pattern=r"^\d{2}$")


class Pueblo(_GeoBase):
    level: Literal[GeoLevel.pueblo] = GeoLevel.pueblo
    codigo_ine: str | None = Field(
        default=None,
        pattern=r"^\d{5}$",
        description="Código municipio INE (5 dígitos).",
    )
    comarca: ComarcaInfo | None = None
    subcomarca: ComarcaInfo | None = None
    centroid: Centroid | None = None
