# API

## Endpoints implementados

### Healthcheck

<div class="api-endpoints" markdown>

| Método | Ruta | Descripción |
|---|---|---|
| <span class="api-method get">GET</span> | `/api/health` | Estado del servidor. |

</div>

### Geografía

<div class="api-endpoints" markdown>

| Método | Ruta | Descripción |
|---|---|---|
| <span class="api-method get">GET</span> | `/api/tree` | Árbol completo CCAA → Provincia → Pueblo. |
| <span class="api-method get">GET</span> | `/api/geo/{geo_id}` | Detalle de una unidad geográfica por UUID. |
| <span class="api-method get">GET</span> | `/api/geo/by-path?path=...` | Unidad geográfica por path ltree (ej. `andalucia.granada.pampaneira`). |

</div>

### Items

<div class="api-endpoints" markdown>

| Método | Ruta | Descripción |
|---|---|---|
| <span class="api-method get">GET</span> | `/api/items` | Listado filtrado (`geo`, `kind`, `status`, `platform`, `source_type`…). |
| <span class="api-method get">GET</span> | `/api/items/{item_id}` | Detalle de un item. |

</div>

### Songs

<div class="api-endpoints" markdown>

| Método | Ruta | Descripción |
|---|---|---|
| <span class="api-method get">GET</span> | `/api/songs` | Listado de canciones. |
| <span class="api-method get">GET</span> | `/api/songs/{song_id}` | Canción con items y relaciones. |

</div>

### Discos

<div class="api-endpoints" markdown>

| Método | Ruta | Descripción |
|---|---|---|
| <span class="api-method get">GET</span> | `/api/discos` | Listado de ediciones discográficas. |
| <span class="api-method get">GET</span> | `/api/discos/{disco_id}` | Detalle de disco con tracks y segmentos. |
| <span class="api-method get">GET</span> | `/api/discos/{disco_id}/tracks` | Tracks de un disco. |
| <span class="api-method get">GET</span> | `/api/tracks/{track_id}/segments` | Segmentos de un track. |

</div>

### Media (streaming)

<div class="api-endpoints" markdown>

| Método | Ruta | Descripción |
|---|---|---|
| <span class="api-method get">GET</span> | `/api/media/{item_id}` | Binario con soporte HTTP Range. |
| <span class="api-method get">GET</span> | `/api/media/{item_id}/embed` | Embed para URLs externas (Spotify, YouTube…). |
| <span class="api-method get">GET</span> | `/api/media/disco-track/{track_id}` | Binario de un track de disco con HTTP Range. |

</div>

---

## Endpoints planificados

### Artistas

<div class="api-endpoints" markdown>

| Método | Ruta | Descripción |
|---|---|---|
| <span class="api-method get">GET</span> | `/api/artists` | Listado de artistas. |
| <span class="api-method get">GET</span> | `/api/artists/{artist_id}` | Detalle de artista + discos. |
| <span class="api-method post">POST</span> | `/api/artists` | Crea un artista. |
| <span class="api-method put">PUT</span> | `/api/artists/{artist_id}` | Actualiza un artista. |
| <span class="api-method delete">DELETE</span> | `/api/artists/{artist_id}` | Borra un artista (`artist_id` en discos queda NULL). |

</div>

### Búsqueda

<div class="api-endpoints" markdown>

| Método | Ruta | Descripción |
|---|---|---|
| <span class="api-method get">GET</span> | `/api/search?q=...` | FTS5 sobre título, intérpretes y tags. |
| <span class="api-method post">POST</span> | `/api/resolve-url` | Pega URL → metadata pre-rellenada. |

</div>

### Edición

<div class="api-endpoints" markdown>

| Método | Ruta | Descripción |
|---|---|---|
| <span class="api-method post">POST</span> | `/api/items` | Crea un item. |
| <span class="api-method put">PUT</span> | `/api/items/{item_id}` | Actualiza campos top-level. |
| <span class="api-method post">POST</span> | `/api/items/{item_id}/refetch` | Refresca `external_metadata`. |
| <span class="api-method delete">DELETE</span> | `/api/items/{item_id}` | Borra un item. |

</div>

---

## Convención de colores

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
