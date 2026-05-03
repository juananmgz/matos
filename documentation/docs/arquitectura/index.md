# Arquitectura

MATOS es un subconjunto del sistema MNEMOSINE pensado para correr **local** y
sin dependencias pesadas (sin Postgres, sin S3, sin auth multiusuario).

## Stack

=== "Backend"

    - **FastAPI 0.115** + **Python 3.12**
    - **Pydantic v2** — fuente de verdad de los esquemas
    - **SQLite** — índice derivado del filesystem
    - **uv** — gestión de dependencias y entorno
    - **typer** — CLI

=== "Frontend"

    - **React 18** + **Vite** + **TypeScript**
    - **PWA-capable** (instalable en móvil)
    - Cliente API generado desde OpenAPI

=== "Datos"

    - Filesystem `archivo/` como **source-of-truth**
    - JSON sidecars (`*.meta.json`, `*.song.json`, `_pueblo.json`…)
    - Índice SQLite **regenerable** con `make reindex`

=== "Despliegue"

    - **Docker Compose** (dev y prod)
    - **Caddy 2** como reverse proxy con HTTPS automático

## Principios de diseño

!!! quote "Filesystem como fuente de verdad"
    Toda la información persistente vive en `archivo/` como JSON. El SQLite
    es **caché de queries**: se borra y se reconstruye sin pérdida. Esto
    permite editar a mano, hacer `git diff` de la documentación, y migrar
    a Postgres+S3 sin reescribir la lógica.

!!! quote "Dos capas de metadatos por item"
    `external_metadata` (cache crudo de Spotify/YouTube) **nunca se edita
    a mano**. Los campos top-level (`title`, `geo_id`, `context`) son la
    verdad del archivo y **nunca se sobrescriben** por refetch.

!!! quote "UUIDs estables"
    Los IDs son UUID v4 generados al crear cada entidad. Renombrar
    archivos o mover carpetas no rompe relaciones.

## Layout del filesystem

```text
archivo/
├── _index.json                          # metadatos del archivo (schema_version)
├── andalucia/
│   ├── _ccaa.json
│   ├── granada/
│   │   ├── _provincia.json
│   │   ├── pampaneira/
│   │   │   ├── _pueblo.json             # comarca, INE, geo
│   │   │   ├── items/
│   │   │   │   ├── 7f3a-…-romance.flac
│   │   │   │   ├── 7f3a-…-romance.meta.json
│   │   │   │   └── 4d2e-…-yt.url.meta.json
│   │   │   └── songs/
│   │   │       └── songs-romance-de-la-loba.song.json
```

## Próximos pasos

- [Base de datos](base-de-datos.md) — esquema SQLite + diagrama ER.
- [Modelo de metadatos](modelo-metadatos.md) — estructura de items, songs, capas externo↔archivo.
