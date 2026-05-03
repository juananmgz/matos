# API

!!! warning "Llega en fase 3"
    Los endpoints todavía no existen. Esta página se rellenará a medida
    que se implementen.

## Endpoints planificados

### Lectura (fase 3)

<div class="api-endpoints" markdown>

| Método | Ruta | Descripción |
|---|---|---|
| <span class="api-method get">GET</span> | `/api/health` | Healthcheck. |
| <span class="api-method get">GET</span> | `/api/tree` | Árbol completo CCAA → Provincia → Pueblo. |
| <span class="api-method get">GET</span> | `/api/tree/{path}` | Subárbol bajo un path ltree. |
| <span class="api-method get">GET</span> | `/api/items/{id}` | Detalle de un item. |
| <span class="api-method get">GET</span> | `/api/items?geo=...&kind=...&status=...` | Listado filtrado. |
| <span class="api-method get">GET</span> | `/api/songs/{id}` | Song con items y relaciones. |
| <span class="api-method get">GET</span> | `/api/pueblo/{path}` | Items y songs de un pueblo. |
| <span class="api-method get">GET</span> | `/api/artists` | Listado de artistas. |
| <span class="api-method get">GET</span> | `/api/artists/{id}` | Detalle de artista + discos. |
| <span class="api-method get">GET</span> | `/api/search?q=...` | FTS5 sobre items. |

</div>

### Streaming (fase 4)

<div class="api-endpoints" markdown>

| Método | Ruta | Descripción |
|---|---|---|
| <span class="api-method get">GET</span> | `/api/items/{id}/media` | Servido con HTTP Range. |
| <span class="api-method post">POST</span> | `/api/resolve-url` | Pega URL → metadata pre-rellenada. |

</div>

### Edición (fase 9)

<div class="api-endpoints" markdown>

| Método | Ruta | Descripción |
|---|---|---|
| <span class="api-method post">POST</span> | `/api/items` | Crea un item. |
| <span class="api-method put">PUT</span> | `/api/items/{id}` | Actualiza campos top-level. |
| <span class="api-method post">POST</span> | `/api/items/{id}/refetch` | Refresca `external_metadata`. |
| <span class="api-method delete">DELETE</span> | `/api/items/{id}` | Borra un item. |
| <span class="api-method post">POST</span> | `/api/artists` | Crea un artista. |
| <span class="api-method put">PUT</span> | `/api/artists/{id}` | Actualiza un artista. |
| <span class="api-method delete">DELETE</span> | `/api/artists/{id}` | Borra un artista (los discos quedan con `artist_id` NULL). |

</div>

## Convención de colores

Cada fila se colorea según el verbo HTTP:

<div class="api-endpoints" markdown>

| Método | Significado | Uso |
|---|---|---|
| <span class="api-method post">POST</span> | Crear (`create`) | Alta de recurso o acción no idempotente. |
| <span class="api-method get">GET</span> | Leer (`read`) | Lectura idempotente, sin efectos. |
| <span class="api-method put">PUT</span> | Actualizar (`update`) | Reemplazo idempotente. `PATCH` se trata igual. |
| <span class="api-method delete">DELETE</span> | Borrar (`delete`) | Borrado idempotente. |

</div>

## OpenAPI

FastAPI genera OpenAPI automáticamente en:

- **JSON**: `http://localhost:8000/openapi.json`
- **Swagger UI**: `http://localhost:8000/docs`
- **ReDoc**: `http://localhost:8000/redoc`
