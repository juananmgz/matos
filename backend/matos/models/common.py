"""Constantes y base común de los modelos."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict

# Versión del esquema de datos. Bump cuando hay un cambio breaking en cualquier
# modelo y escribir migración. Independiente de __version__ del paquete.
SCHEMA_VERSION = "1.0.0"


class MatosModel(BaseModel):
    """Base de todos los modelos MATOS.

    - `extra="ignore"` para que JSONs antiguos con campos eliminados no rompan.
    - `validate_assignment=True` valida también al asignar atributos.
    - `str_strip_whitespace=True` quita whitespace de strings al validar.
    """

    model_config = ConfigDict(
        extra="ignore",
        validate_assignment=True,
        str_strip_whitespace=True,
        use_enum_values=False,  # mantiene el enum como objeto, no como str
    )
