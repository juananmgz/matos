# MATOS

Reproductor del archivo de etnomusicología **MNEMOSINE**.
Primera aplicación independiente del proyecto MNEMOSINE.

> Para contexto del sistema completo ver `../arquitectura_archivo_etnomusicologico.md`.

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
- Frontend (vite dev): http://localhost:5173
- Caddy HTTPS: https://localhost (cert interno; aceptar warning la primera vez)

## Comandos

```bash
make help                               # lista todos los comandos
make up                                 # arranca dev
make down                               # para
make logs s=backend                     # tail logs de un servicio
make shell                              # bash en backend (s=frontend para frontend)
make test                               # tests
make lint                               # lint backend + frontend
make format                             # auto-format
make reindex                            # reconstruye índice SQLite (fases ≥2)
make up-prod                            # arranca con imágenes de producción
make build                              # build prod tagged con git sha
make backup                             # tar archivo/ + dump índice
make clean                              # ⚠ borra volúmenes (venv, node_modules)
```

## Estructura

```
MATOS/
├── backend/           # FastAPI + Pydantic v2 + uv
├── frontend/          # React + Vite + TypeScript + pnpm
├── docker/            # Dockerfiles y Caddyfile
├── scripts/           # wrappers de docker compose
├── archivo/           # datos (gitignored, montado como volumen)
├── docker-compose.yml         # base
├── docker-compose.override.yml # dev (auto)
├── docker-compose.prod.yml     # prod (explícito)
└── Makefile
```

## Flujo de desarrollo

1. Edita el código en tu IDE en el host como siempre.
2. Hot reload se dispara dentro del contenedor:
   - Backend: uvicorn `--reload` detecta cambios en `backend/matos/`
   - Frontend: Vite HMR detecta cambios en `frontend/src/`
3. `make test` y `make lint` siempre dentro del contenedor.

Para entrar al contenedor: `make shell` (backend) o `make shell s=frontend`.

VSCode/Cursor: "Reopen in Container" abre el editor dentro del contenedor (config en `.devcontainer/`).

## Estado

**Fase 0 completada.** Hello-world FastAPI + Vite, todo dockerizado, Makefile, devcontainer. Siguientes fases en `CLAUDE.md`.
