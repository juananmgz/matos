"""CLI de MATOS — utilidades del archivo etnomusicológico."""

from __future__ import annotations

import json
from pathlib import Path

import typer

from . import __version__
from .models import (
    CCAA,
    SCHEMA_VERSION,
    ArchiveIndex,
    Item,
    Provincia,
    Pueblo,
    Song,
)

app = typer.Typer(
    name="matos",
    help="MATOS — utilidades del archivo etnomusicológico.",
    no_args_is_help=True,
)


@app.command()
def version() -> None:
    """Muestra versión del paquete y del schema."""
    typer.echo(f"matos        {__version__}")
    typer.echo(f"schema       {SCHEMA_VERSION}")


@app.command()
def hello() -> None:
    """Smoke test."""
    typer.echo("MATOS CLI activo.")


@app.command(name="export-schemas")
def export_schemas(
    output: Path = typer.Argument(  # noqa: B008
        Path("/app/schemas"),
        help="Directorio destino para los JSON Schema generados.",
    ),
) -> None:
    """Genera los JSON Schemas (espejo de los modelos Pydantic).

    Los `schemas/*.schema.json` resultantes son consumidos por el editor del
    frontend para validación en cliente. **Nunca editar a mano**: regenerar
    con este comando tras cambios en los modelos.
    """

    output.mkdir(parents=True, exist_ok=True)

    models = {
        "ccaa": CCAA,
        "provincia": Provincia,
        "pueblo": Pueblo,
        "item": Item,
        "song": Song,
        "index": ArchiveIndex,
    }

    for name, model in models.items():
        schema = model.model_json_schema()
        schema["$id"] = f"https://matos.local/schemas/{name}.schema.json"
        schema["$schema"] = "https://json-schema.org/draft/2020-12/schema"
        path = output / f"{name}.schema.json"
        path.write_text(
            json.dumps(schema, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
        typer.echo(f"  ✓ {path}")

    typer.echo(f"\n{len(models)} schemas escritos en {output}/")


# ─── Stubs para fases siguientes ─────────────────────────────────────────────


@app.command()
def init(path: str = "/data/archivo") -> None:
    """[fase 2] Crea estructura mínima del archivo en PATH."""
    typer.echo(f"[no implementado — fase 2] init {path}")
    raise typer.Exit(code=1)


@app.command()
def validate(path: str = "/data/archivo") -> None:
    """[fase 2] Valida todos los JSON del archivo contra los schemas Pydantic."""
    typer.echo(f"[no implementado — fase 2] validate {path}")
    raise typer.Exit(code=1)


@app.command()
def reindex() -> None:
    """[fase 2] Reconstruye el índice SQLite desde el filesystem."""
    typer.echo("[no implementado — fase 2] reindex")
    raise typer.Exit(code=1)


if __name__ == "__main__":
    app()
