# API

!!! warning "Llega en fase 3"
    Los endpoints todavía no existen. Esta página se rellenará a medida
    que se implementen.

## Endpoints planificados

### Lectura (fase 3)

| Método | Ruta | Descripción |
|---|---|---|
| `GET` | `/api/health` | Healthcheck. |
| `GET` | `/api/tree` | Árbol completo CCAA → Provincia → Pueblo. |
| `GET` | `/api/tree/{path}` | Subárbol bajo un path ltree. |
| `GET` | `/api/items/{id}` | Detalle de un item. |
| `GET` | `/api/items?geo=...&kind=...&status=...` | Listado filtrado. |
| `GET` | `/api/songs/{id}` | Song con items y relaciones. |
| `GET` | `/api/pueblo/{path}` | Items y songs de un pueblo. |
| `GET` | `/api/search?q=...` | FTS5 sobre items. |

### Streaming (fase 4)

| Método | Ruta | Descripción |
|---|---|---|
| `GET` | `/api/items/{id}/media` | Servido con HTTP Range. |
| `POST` | `/api/resolve-url` | Pega URL → metadata pre-rellenada. |

### Edición (fase 9)

| Método | Ruta | Descripción |
|---|---|---|
| `PUT` | `/api/items/{id}` | Actualiza campos top-level. |
| `POST` | `/api/items/{id}/refetch` | Refresca `external_metadata`. |

## OpenAPI

FastAPI genera OpenAPI automáticamente en:

- **JSON**: `http://localhost:8000/openapi.json`
- **Swagger UI**: `http://localhost:8000/docs`
- **ReDoc**: `http://localhost:8000/redoc`
