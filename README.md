# MATOS

Reproductor y catalogador del archivo de etnomusicología **MNEMOSINE**.
Primera aplicación independiente del proyecto MNEMOSINE; diseñada para
integrarse con los módulos posteriores sin reescritura.

> Para contexto del sistema completo ver `../arquitectura_archivo_etnomusicologico.md`.  
> Plan de fases detallado en [`ROADMAP.md`](ROADMAP.md).

## Requisitos en el host

| OS | Necesario | Recomendado |
|---|---|---|
| macOS | Docker Desktop **o** OrbStack | OrbStack (I/O 10× más rápido sobre bind mounts) |
| Linux | Docker Engine + Compose v2 | — |
| Windows | Docker Desktop + WSL2 | Repo dentro del filesystem WSL2, no `/mnt/c` |
| Todos | Make + Git | — |

**No se requiere Python, Node, uv, ni pnpm en el host.** Todo corre en contenedores.

## Quickstart

```bash
git clone <repo-url> MATOS
cd MATOS
cp .env.example .env                    # rellenar secretos cuando aplique
make lock                               # primera vez: genera uv.lock + pnpm-lock.yaml
make up                                 # arranca dev (build automático)
```

URLs:
- Backend API: http://localhost:8000/api/health
- Frontend (Vite dev): http://localhost:5173
- Caddy HTTPS: https://localhost (cert interno; aceptar warning la primera vez)

## Comandos

```bash
make help                               # lista todos los comandos

# ciclo de vida
make up                                 # arranca dev
make down                               # para
make logs s=backend                     # tail logs de un servicio
make shell                              # bash en backend (s=frontend para frontend)
make restart s=backend                  # reinicia un servicio

# tests, lint, format
make test                               # tests backend + frontend
make lint                               # lint backend + frontend
make format                             # auto-format

# archivo (datos)
make init                               # inicializa archivo/ con _index.json + CCAA ejemplo
make validate                           # valida todos los JSON del archivo
make reindex                            # reconstruye índice SQLite desde el filesystem
make new-pueblo args="--ccaa X --provincia Y Nombre"
make new-item   args="<pueblo-path> <fichero|url>"
make export-schemas                     # regenera schemas/*.schema.json

# producción
make up-prod                            # arranca con imágenes de producción
make build                              # build prod tagged con git sha
make release                            # push a $REGISTRY

# documentación
make db-diagram                         # regenera documentation/db-schema.png

# mantenimiento
make backup                             # tar archivo/ + dump índice
make clean                              # ⚠ borra volúmenes (venv, node_modules, índice)
```

## Estructura

```
MATOS/
├── backend/
│   ├── matos/
│   │   ├── main.py              # FastAPI app + /api/health
│   │   ├── config.py            # settings (pydantic-settings, env vars MATOS_*)
│   │   ├── cli.py               # typer CLI (init, validate, reindex, export-schemas)
│   │   ├── models/              # Pydantic v2: GeoUnit, Huerfanas, Item, Song, Disco, DiscoTrack, ArchiveIndex
│   │   ├── storage/             # StorageAdapter (base) + LocalStorage (filesystem)
│   │   └── index/               # SQLite: schema.sql, builder.py, queries.py
│   └── tests/                   # pytest (54 tests)
├── frontend/                    # React 18 + Vite + TypeScript (fase 5+)
├── docker/                      # Dockerfiles + Caddyfile
├── scripts/                     # lock, backup, restore, release
├── schemas/                     # JSON Schema generado desde Pydantic (make export-schemas)
├── documentation/               # db-schema.dot + db-schema.png (ER diagram)
├── archivo/                     # datos del archivo (gitignored)
├── docker-compose.yml
├── docker-compose.override.yml  # dev (auto)
├── docker-compose.prod.yml      # prod (explícito)
└── Makefile
```

## Modelo de datos

Entidades almacenadas como JSON sidecars en `archivo/`:

- **GeoUnit** (`_ccaa.json` / `_provincia.json` / `_pueblo.json` / `_huerfanas.json`): jerarquía geográfica CCAA → Provincia → Pueblo bajo `archivo/geo/`. `_huerfanas/` puede vivir en cualquier nivel para canciones de origen geográfico parcialmente conocido.
- **Item** (`<uuid>.meta.json`): unidad atómica — audio, vídeo, partitura, letra o URL externa.
- **Song** (`<uuid>.song.json`): canción canónica que agrupa items y declara relaciones entre ellos.
- **Disco** (`_disco.json`) + **DiscoTrack** (`metadatos/<...>.track.json`): edición discográfica bajo `archivo/discos/<artista>/(YYYY) titulo/`. Cada track contiene 1+ **TrackSegment**s que mapean tramos de audio a `Song`s del archivo geográfico (bidireccional).

El índice SQLite (`/data/index/matos.db`) es **derivado** del filesystem y se reconstruye con `make reindex`. Ver esquema en [`documentation/db-schema.png`](documentation/db-schema.png).

## Flujo de desarrollo

1. Edita código en el host con tu IDE favorito.
2. Hot reload se dispara dentro del contenedor:
   - Backend: uvicorn `--reload` detecta cambios en `backend/matos/`
   - Frontend: Vite HMR detecta cambios en `frontend/src/`
3. `make test` y `make lint` siempre dentro del contenedor.

Para entrar al contenedor: `make shell` (backend) o `make shell s=frontend`.  
VSCode/Cursor: "Reopen in Container" abre el editor dentro del contenedor (`.devcontainer/`).

## Estado de fases

| # | Fase | Estado |
|---|---|---|
| 0 | Scaffold + dockerización | ✅ |
| 1 | Schemas Pydantic + JSON Schema export | ✅ |
| 1.5 | Discos + huérfanas (layout `geo/` + `discos/`) | ✅ |
| 2 | Storage local + índice SQLite | ✅ |
| 3 | API lectura (tree, items, songs) | ⏳ |
| 4 | API streaming + URL resolution | ⏳ |
| 5 | Frontend navegación jerárquica | ⏳ |
| 6 | Player + Media Session API | ⏳ |
| 7 | Vista Song | ⏳ |
| 8 | PWA + diseño móvil + A2DP/AVRCP | ⏳ |
| 9 | Editor de metadatos | ⏳ |
| … | … | ⏳ |

Plan completo en [`ROADMAP.md`](ROADMAP.md).
