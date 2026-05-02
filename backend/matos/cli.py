"""CLI de MATOS — utilidades del archivo etnomusicológico."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

import typer

from . import __version__
from .config import settings
from .index import build_index, validate_archive
from .models import (
    CCAA,
    SCHEMA_VERSION,
    ArchiveIndex,
    Disco,
    DiscoTrack,
    Huerfanas,
    Item,
    Provincia,
    Pueblo,
    Song,
)
from .storage import LocalStorage

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
        "huerfanas": Huerfanas,
        "item": Item,
        "song": Song,
        "disco": Disco,
        "disco_track": DiscoTrack,
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


# ─── Archivo: init / validate / reindex ─────────────────────────────────────


@app.command()
def init(
    path: Path = typer.Argument(  # noqa: B008
        Path("/data/archivo"),
        help="Raíz del archivo a inicializar.",
    ),
    force: bool = typer.Option(False, "--force", help="Sobrescribe _index.json existente."),
) -> None:
    """Crea estructura mínima del archivo: `_index.json` + CCAA de ejemplo."""

    storage = LocalStorage(path)
    storage.root.mkdir(parents=True, exist_ok=True)

    index_path = "_index.json"
    if storage.exists(index_path) and not force:
        typer.echo(f"✗ {path}/_index.json ya existe (usa --force para sobrescribir).")
        raise typer.Exit(code=1)

    now = datetime.now(UTC)
    archive = ArchiveIndex(
        schema_version=SCHEMA_VERSION,
        archive_name="MATOS",
        description="Archivo etnomusicológico MNEMOSINE — MATOS.",
        created_at=now,
        updated_at=now,
    )
    storage.write_text(
        index_path,
        archive.model_dump_json(indent=2, exclude_none=True) + "\n",
    )

    # CCAA de ejemplo: Andalucía bajo `geo/`. Usuario puede borrarla y crear las suyas.
    ccaa_dir = "geo/andalucia"
    if not storage.exists(ccaa_dir):
        ccaa = CCAA(id=uuid4(), nombre="Andalucía", codigo="01")
        storage.write_text(
            f"{ccaa_dir}/_ccaa.json",
            ccaa.model_dump_json(indent=2, exclude_none=True) + "\n",
        )
        typer.echo(f"  ✓ {path}/{ccaa_dir}/_ccaa.json")

    # Carpeta `discos/` vacía como ancla para el layout (fase 1.5).
    discos_anchor = "discos/.gitkeep"
    if not storage.exists(discos_anchor):
        storage.write_text(discos_anchor, "")
        typer.echo(f"  ✓ {path}/discos/")

    typer.echo(f"  ✓ {path}/_index.json")
    typer.echo(f"\nArchivo inicializado en {path}.")


@app.command()
def validate(
    path: Path = typer.Argument(  # noqa: B008
        Path("/data/archivo"),
        help="Raíz del archivo a validar.",
    ),
) -> None:
    """Valida todos los JSON del archivo contra los schemas Pydantic.

    No toca el índice SQLite. Sale con código 1 si hay errores.
    """
    storage = LocalStorage(path)
    if not storage.exists("."):
        typer.echo(f"✗ {path} no existe.")
        raise typer.Exit(code=1)

    report = validate_archive(storage)
    _print_report(report)
    if not report.ok:
        raise typer.Exit(code=1)


@app.command()
def reindex(
    path: Path = typer.Option(  # noqa: B008
        None,
        "--archive",
        help="Raíz del archivo. Por defecto, MATOS_ARCHIVE_PATH.",
    ),
    db: Path = typer.Option(  # noqa: B008
        None,
        "--db",
        help="Destino SQLite. Por defecto, MATOS_INDEX_PATH.",
    ),
) -> None:
    """Reconstruye el índice SQLite desde cero leyendo el archivo."""
    archive_path = path or settings.archive_path
    db_path = db or settings.index_path

    storage = LocalStorage(archive_path)
    if not storage.exists("."):
        typer.echo(f"✗ {archive_path} no existe.")
        raise typer.Exit(code=1)

    typer.echo(f"Construyendo índice desde {archive_path} → {db_path}…")
    report = build_index(storage, db_path)
    _print_report(report)
    if not report.ok:
        typer.echo("✗ Errores; índice NO actualizado.")
        raise typer.Exit(code=1)
    typer.echo(f"✓ Índice escrito en {db_path}")


def _print_report(report) -> None:  # noqa: ANN001
    """Imprime resumen del IndexReport."""
    typer.echo(
        f"  CCAA: {report.ccaa}  Provincias: {report.provincias}  "
        f"Pueblos: {report.pueblos}  Huérfanas: {report.huerfanas}"
    )
    typer.echo(f"  Items: {report.items}  Songs: {report.songs}  Relaciones: {report.relations}")
    typer.echo(
        f"  Discos: {report.discos}  Tracks: {report.disco_tracks}  "
        f"Segmentos: {report.track_segments}"
    )
    if report.errors:
        typer.echo(f"\n✗ {len(report.errors)} errores:")
        for err in report.errors:
            typer.echo(f"    - {err}")


if __name__ == "__main__":
    app()
