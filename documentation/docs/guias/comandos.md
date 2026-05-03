# Referencia de comandos

Todos los comandos pasan por `make` y se ejecutan dentro de contenedores.

## Ciclo de vida

| Comando | Descripción |
|---|---|
| `make help` | Lista todos los comandos disponibles. |
| `make up` | Arranca dev (build automático). |
| `make down` | Para dev. |
| `make logs s=backend` | Tail de logs (`s=` selecciona servicio). |
| `make shell` | Bash en backend (`s=frontend` para frontend). |
| `make restart s=backend` | Reinicia un servicio. |
| `make ps` | Estado de los servicios. |

## Tests, lint, format

| Comando | Descripción |
|---|---|
| `make test` | Tests backend (pytest) + frontend (vitest). |
| `make lint` | Lint backend (ruff) + frontend (eslint). |
| `make format` | Auto-format backend + frontend. |

## Archivo de datos

| Comando | Descripción |
|---|---|
| `make init` | Inicializa `archivo/` con `_index.json` + CCAA ejemplo. |
| `make validate` | Valida todos los JSON contra los schemas Pydantic. |
| `make reindex` | Reconstruye el índice SQLite. |
| `make new-pueblo args="..."` | Crea un pueblo en el archivo. |
| `make new-item args="..."` | Crea un item (audio/url/...). |
| `make export-schemas` | Regenera `schemas/*.schema.json`. |

## Documentación

| Comando | Descripción |
|---|---|
| `make docs` | Arranca este sitio en <http://localhost:8001>. |
| `make docs-build` | Genera el sitio estático en `documentation/site/`. |
| `make db-diagram` | Regenera `documentation/docs/assets/db-schema.png`. |

## Producción

| Comando | Descripción |
|---|---|
| `make up-prod` | Arranca con imágenes de producción. |
| `make build` | Build prod tagged con git sha. |
| `make release` | Push a `$REGISTRY`. |

## Mantenimiento

| Comando | Descripción |
|---|---|
| `make backup` | Tar de `archivo/` + dump del índice. |
| `make restore args="<fichero>"` | Restaura backup. |
| `make clean` | :material-alert: Borra volúmenes (.venv, node_modules, índice). |
| `make rebuild` | Rebuild forzado de las imágenes dev. |
