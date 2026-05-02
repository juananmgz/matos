# MATOS — Roadmap de fases

Plan de implementación por fases. Una fase = milestone autocontenido. El proyecto avanza
fase a fase con `make test` verde y commit nombrado `feat: phase N — <título>`.

> Ver [CLAUDE.md](CLAUDE.md) para contexto general, stack y convenciones.
> Ver [arquitectura_archivo_etnomusicologico.md](../arquitectura_archivo_etnomusicologico.md)
> para la visión completa de MNEMOSINE en la que MATOS encaja.

## Leyenda

| Símbolo | Estado |
|---|---|
| ✅ | Completada — commits en `main` |
| ▶ | En curso |
| ⏳ | Pendiente |

## Estado actual

| # | Fase | Estado |
|---|---|---|
| 0  | Scaffold + dockerización | ✅ |
| 1  | Schemas Pydantic + JSON Schema export | ✅ |
| 1.5| Discos + huérfanas (layout `geo/` + `discos/`) | ✅ |
| 2  | Storage local + índice SQLite | ✅ |
| 3  | API lectura (tree, items, songs) | ✅ |
| 4  | API streaming + URL resolution | ✅ |
| 5  | Frontend navegación jerárquica | ⏳ |
| 6  | Player + Media Session API | ⏳ |
| 7  | Vista Song (versiones, letras, partituras) | ⏳ |
| 8  | PWA + diseño móvil + A2DP/AVRCP | ⏳ |
| 9  | Editor de metadatos (2 columnas externo↔archivo) | ⏳ |
| 10 | Cola de triaje + edición masiva | ⏳ |
| 11 | Refetch externo + diff visual | ⏳ |
| 12 | Segmentos (multi-canción en un media) | ⏳ |
| 13 | Integración Spotify (OAuth PKCE + Web Playback SDK) | ⏳ |
| 14 | Integración YouTube (IFrame + oEmbed) | ⏳ |
| 15 | Integración Wikimedia/Wikidata | ⏳ |
| 16 | CLI utilidades (init, validate, new-pueblo, new-item) | ⏳ |
| 17 | Búsqueda (FTS5) + filtros multi-criterio | ⏳ |
| 18 | Pulido + despliegue (Tailscale, registry, manual) | ⏳ |

**Total estimado**: ≈ 20 días ingeniero solo. Subset jugable mínimo: fases 0–6 + 9 (~10 días).

---

## Fase 0 ✅ — Scaffold + dockerización

**Objetivo**: repositorio funcional sin instalar nada en host salvo Docker.

**Entregado**:
- FastAPI 0.115 (uv + Python 3.12) con `/api/health`.
- React 18 + Vite + TypeScript frontend.
- Caddy 2 reverse proxy con HTTPS interno.
- Docker Compose multi-stage: `dev` (hot reload, bind mounts de subcarpetas) y `prod` (4 workers, sin source mounts).
- `Makefile` + `scripts/` (lock, backup, restore, release).
- `.devcontainer/` para VSCode/Cursor.

**Comandos clave**:
```bash
make lock     # 1ª vez: genera uv.lock + pnpm-lock.yaml
make up       # arranca dev
make ps       # estado servicios
make test     # tests dentro del contenedor
make logs s=backend
```

**Lecciones aprendidas** (registradas para futuras decisiones):
- En `docker-compose.override.yml` solo bind-montear **subcarpetas** específicas, no carpetas raíz ni ficheros que aún no existen — Docker crea directorios vacíos para bind mounts huérfanos (causa: EISDIR en `pnpm install`, pyproject lock issues).
- `.venv` y `node_modules` viven dentro de la imagen, no en volúmenes nombrados ni en bind mounts. Volúmenes nombrados taparon `.venv` con contenido obsoleto en una iteración.
- uv 0.4.20 NO soporta PEP 735 `[dependency-groups]`. Usar `[tool.uv.dev-dependencies]` para dev deps. Plan: bumpear uv cuando integremos features que lo requieran.
- Caddyfile usa `tls internal` con `local_certs`; aceptar warning del navegador la 1ª vez. Para Let's Encrypt real (fase 18), pasar a `tls internal` → `tls {dominio}` con DNS challenge.

---

## Fase 1 ✅ — Schemas Pydantic + JSON Schema export

**Objetivo**: modelo de datos canónico, validable, exportable como JSON Schema para que el editor frontend valide en cliente.

**Entregado**:
- `models/geo.py`: `CCAA`, `Provincia`, `Pueblo`, `ComarcaInfo` con `ComarcaTipo` enumerado por origen (legal/funcional/etnomusicologica/manual), `Centroid`.
- `models/item.py`: `Item`, `ItemContext`, `ItemSource` (con `ReleaseInfo` y `BroadcastInfo`), `Rights`, `Segment`, `Lugar`, `ExternalMetadata`, `EnrichmentInfo`.
- `models/song.py`: `Song`, `Relation`, `RelationType` (6 tipos: version_of, lyrics_of, score_of, cover_of, derived_from, same_as).
- `models/index.py`: `ArchiveIndex` (raíz `archivo/_index.json`).
- `models/common.py`: `MatosModel` base + `SCHEMA_VERSION = "1.0.0"`.
- 28 tests pytest verdes incluyendo:
  - Caso "Ringorrango — J#4" (verdad externa preservada en `external_metadata.raw` + `track_title_external`; verdad del archivo en `title`/`geo_id`/`context`).
  - Invariantes `kind ↔ file/url`, `source.type ↔ release/broadcast`.
  - Validación de rangos: lat/lon, INE 5/2 dígitos, year, segments.
  - Self-loops en relaciones rechazados.
  - Roundtrip JSON: model → dump → load → equals.
  - `compute_status`: pending/partial/complete según campos rellenos.
- CLI `matos export-schemas` → `schemas/*.schema.json` (6 ficheros).
- Mount `./schemas:/app/schemas:rw` en override; `make export-schemas` desde host.

**Decisiones de diseño**:
- **Dos capas de metadatos por item**: `external_metadata` (cache crudo, inmutable a mano, solo via refetch) vs. campos top-level (verdad del archivo, editada por superusuario). `external_metadata.raw_hash` permite detectar `needs_review` en fase 11.
- **`Segment` permite multi-canción en un mismo media**: ítems hermanos con la misma URL y distinto `offset_s`/`duration_s` para medleys o álbum-tracks.
- **`geo_id` del item = origen de la canción**, no ubicación del artista (clave para el caso Ringorrango).
- **Identidad por UUID v4 estable**: renombrar ficheros no rompe relaciones.

---

## Fase 1.5 ✅ — Discos + huérfanas

**Objetivo**: ampliar el modelo conceptual con discos (LP/CD/EP/single/digital)
y con un mecanismo de geo parcial (huérfanas), permitiendo bidireccionalidad
entre tramos de tracks de un disco y canciones tradicionales por pueblo.

**Reorganización del layout**: `archivo/<ccaa>/...` → `archivo/geo/<ccaa>/...`.
Nueva carpeta hermana `archivo/discos/<artista>/(YYYY) titulo/`.

**Entregado**:
- `models/disco.py`: `Disco`, `DiscoFormato`, `DiscoTrack`, `TrackSegment` con
  `offset_s`/`duration_s` opcionales (track entero = segmento sin offsets).
- `models/geo.py`: nueva `Huerfanas` (level `huerfanas`); válido a nivel raíz,
  CCAA o provincia.
- `models/song.py`: campo `original_recording_missing: bool` para stubs creados
  desde un `TrackSegment` sin grabación de campo.
- `index/schema.sql`: tablas `disco`, `disco_track`, `track_segment`; columna
  `original_recording_missing` en `song`; level enum extendido en `geo_unit`.
- `index/builder.py`: walker reescrito sobre `archivo/geo/` + `archivo/discos/`.
  Soporta `_huerfanas/` en cualquier nivel (UUID estable derivado del path si
  falta `_huerfanas.json`). Validación FK explícita de `track_segment.song_id`.
- `index/queries.py`: `get_disco`, `list_discos`, `tracks_of_disco`,
  `segments_of_track`, `disco_segments_of_song` (lookup inverso).
- `cli.py`: `init` crea `geo/andalucia/` y `discos/.gitkeep`. `export-schemas`
  incluye `huerfanas`, `disco`, `disco_track`.
- 8 tests nuevos cubriendo: huérfanas en provincia y raíz; ingest de disco con
  3 segmentos; lookup inverso `disco_segments_of_song`; segmento huérfano con
  `unmatched=true`; errores por song_id inexistente y binario faltante.

**Bidireccionalidad**:
- Lado disco (fuente de verdad): `*.track.json` declara segmentos con
  `song_id` opcional + flag `unmatched: bool`.
- Lado geo: si la canción no existe, se crea `Song` *stub* en el nivel más
  fino conocido (pueblo / `_huerfanas` de provincia / `_huerfanas` de CCAA /
  `_huerfanas` raíz) con `original_recording_missing=true`.
- Consulta inversa por SQL: `track_segment` indexada por `song_id`.

**Pendiente para fases posteriores**:
- CLI `make new-disco`, `make import-disco`, `make new-segment` (fase 16
  amplía el alcance de utilidades).
- Editor visual con waveform + handles arrastrables para mapear segmento↔Song
  (fase 9 + fase 12 — ver memoria `project_disco_segment_editor`).

---

## Fase 2 ✅ — Storage local + índice SQLite

**Objetivo**: leer/escribir el filesystem `archivo/` y construir un índice SQLite consultable.

**Pre-requisitos**: fase 1.

**Entregables**:
- `backend/matos/storage/base.py` — interfaz `StorageAdapter` (open/list/exists/write/sha256).
- `backend/matos/storage/local.py` — implementación filesystem.
- `backend/matos/index/schema.sql` — DDL SQLite (tablas `geo_unit`, `item`, `song`, `relation`, FTS5 virtual table).
- `backend/matos/index/builder.py` — walker: recorre `archivo/`, valida JSONs vía Pydantic, inserta en SQLite.
- `backend/matos/index/queries.py` — funciones de consulta (tree, item-by-id, items-of-pueblo, items-of-song, etc.).
- `aiosqlite` en deps.
- CLI:
  - `matos init <path>` — crea `archivo/_index.json` y la primera CCAA de ejemplo.
  - `matos validate <path>` — valida todos los JSONs sin escribir índice.
  - `matos reindex` — rebuild completo del SQLite.
- `make init`, `make validate`, `make reindex` (ya existen como wrappers en Makefile).
- Tests: `tests/test_storage.py` con fixtures de filesystem temporal, `tests/test_index_builder.py` con archivo de ejemplo end-to-end.

**Diseño**:
- Filesystem layout (recordatorio):
  ```
  archivo/_index.json
  archivo/<ccaa>/_ccaa.json
  archivo/<ccaa>/<provincia>/_provincia.json
  archivo/<ccaa>/<provincia>/<pueblo>/_pueblo.json
  archivo/<ccaa>/<provincia>/<pueblo>/items/<uuid>.meta.json
  archivo/<ccaa>/<provincia>/<pueblo>/items/<uuid>.<ext>
  archivo/<ccaa>/<provincia>/<pueblo>/songs/<uuid>.song.json
  ```
- Path tipo ltree (`andalucia.granada.pampaneira`) calculado al indexar.
- SQLite es **derivado**: nunca leer/escribir manualmente. `make reindex` reconstruye.
- Diseño orientado a migración a Postgres (fase futura MNEMOSINE): mismas tablas, mismas columnas.

**Estimación**: ~1.5 días.

---

## Fase 3 ✅ — API lectura

**Objetivo**: endpoints FastAPI para navegar el archivo desde el frontend.

**Pre-requisitos**: fase 2.

**Entregado**:
- `api/deps.py` — dependencia `get_conn` (sqlite read-only desde `settings.index_path`)
  + `Pagination(limit, offset)`. Override-able vía `app.dependency_overrides[get_db_path]`.
  503 si el índice no existe.
- `api/tree.py` — `GET /api/tree` (árbol completo anidado),
  `GET /api/geo/{id}?include=children,items,songs`,
  `GET /api/geo/by-path?path=…`.
- `api/items.py` — `GET /api/items` con filtros `geo_id`, `song_id`, `kind`,
  `status`, `platform`, `source_type`, `has_external`, `q` (FTS5),
  `limit`/`offset`. `GET /api/items/{id}`.
- `api/songs.py` — `GET /api/songs` filtros `geo_id`, `original_recording_missing`,
  paginación. `GET /api/songs/{id}` incluye `items`, `relations` y
  `disco_segments` (bidireccional disco↔canción).
- `api/discos.py` — `GET /api/discos`, `GET /api/discos/{id}` con tracks +
  segments anidados, `GET /api/discos/{id}/tracks`,
  `GET /api/tracks/{id}/segments`.
- `index/queries.py` extendido: `list_items` (filtros + count), `list_songs`
  (filtros + paginación opcional), `songs_of_geo`.
- 23 tests `test_api_read.py` con TestClient + dependency overrides.
  Reusa fixtures de `test_index_builder.py` (sample_archive, archive_with_disco_and_huerfanas).

**Forma de respuesta paginada** (uniforme):
```json
{ "items": [...], "total": N, "limit": L, "offset": O }
```

**Pendiente para fase 5**: generación de cliente TypeScript desde OpenAPI
(`pnpm generate-api`). El esquema OpenAPI ya está disponible en `/openapi.json`.

---

## Fase 4 ✅ — API streaming + URL resolution

**Objetivo**: servir media local con HTTP Range, devolver embed para URLs externas.

**Pre-requisitos**: fase 3.

**Entregado**:
- `api/media.py`:
  - `GET /api/media/{item_id}` — sirve binario local con `StreamingResponse`
    en chunks de 64 KiB. Soporta `Range: bytes=START-`, `START-END` y suffix
    `-N`. Devuelve 200 con `Accept-Ranges: bytes` o 206 con `Content-Range`.
    416 si el rango está fuera del fichero.
  - `GET /api/media/{item_id}/embed` — `resolve_embed()` con regex por
    plataforma (Spotify track/album/playlist con o sin locale, YouTube
    watch/youtu.be/embed). Devuelve `{type, platform, embed_url,
    external_id, original_url, segment?}`. URLs no reconocidas → `type=link`.
    400 si el item es local; 400 si el item URL no tiene URL.
  - `GET /api/media/disco-track/{track_id}` — análogo al item local pero
    resuelve binario relativo al disco (`<fs_path>.parent.parent / file`).
- `api/deps.py`: `get_archive_root()` override-able en tests.
- Builder: `_ingest_song` ahora hereda `geo_id` de la carpeta cuando no se
  declara explícitamente (consistente con items; necesario para
  `songs_of_geo` en /api/geo/{id}).
- 24 tests `test_api_media.py` (resolver unit + Range completo + endpoints).
- `tests/conftest.py` reexporta fixtures comunes.
- `pyproject.toml`: `flake8-bugbear.extend-immutable-calls` para que ruff
  acepte `Depends/Query/Header/Path/Body` en defaults.

---

## Fase 5 ⏳ — Frontend navegación

**Objetivo**: navegar el archivo desde el navegador con UI básica.

**Pre-requisitos**: fases 3-4.

**Entregables**:
- `frontend/src/api/` — cliente generado desde OpenAPI (`pnpm generate-api`).
- `frontend/src/routes/`:
  - `Browse.tsx` — árbol CCAA → Provincia → Pueblo lateral.
  - `Pueblo.tsx` — vista pueblo con lista de items y songs.
  - `Item.tsx` — detalle de item.
  - `Song.tsx` — vista canción (esqueleto, expandido en fase 7).
- `components/TreeNav.tsx`, `components/ItemList.tsx`, `components/StatusBadge.tsx` (pending/partial/complete/needs_review).
- React Router 6 con rutas anidadas.
- React Query para cache + invalidación.

**Estimación**: ~1.5 días.

---

## Fase 6 ⏳ — Player + Media Session

**Objetivo**: reproducir audio/vídeo local y URL embeds; controles AVRCP funcionando vía Media Session API (clave para A2DP móvil).

**Pre-requisitos**: fases 4-5.

**Entregables**:
- `components/AudioPlayer.tsx` — `<audio>` HTML5 + Media Session API completa (metadata: title/artist/artwork; handlers: play/pause/previoustrack/nexttrack/seekto).
- `components/VideoPlayer.tsx` — `<video>` con misma integración.
- `components/EmbedPlayer.tsx` — iframe Spotify/YouTube; coordinación con Media Session cuando sea posible.
- `integrations/media-session.ts` — helper compartido.
- **Remote Playback API**: `audio.remote.prompt()` para selector AirPlay/Cast.
- Respeto a `segment.offset_s` / `duration_s` en items con segmento.

**Estimación**: ~1.5 días.

---

## Fase 7 ⏳ — Vista Song

**Objetivo**: agrupar y visualizar todas las versiones de una canción.

**Pre-requisitos**: fases 5-6.

**Entregables**:
- `routes/Song.tsx` con: cabecera, lista de versiones (audio/vídeo), letra(s), partitura(s), reproductor cruzado entre items.
- Renderizado de `relations` con flechas/badges (lyrics_of, score_of, version_of).
- Reproducción "siguiente versión" con cola implícita.

**Estimación**: ~1 día.

---

## Fase 8 ⏳ — PWA + móvil

**Objetivo**: instalable en iOS/Android con audio Bluetooth A2DP funcional.

**Pre-requisitos**: fase 6.

**Entregables**:
- `frontend/public/manifest.webmanifest` con icons completos (192, 512, maskable).
- Service worker (Workbox): cache de shell + estrategia network-first para `/api/`.
- Responsive mobile-first: ajustes CSS para `< 768px` con touch targets de 44px+.
- Pantalla de instalación + meta tags iOS (`apple-touch-icon`, `apple-mobile-web-app-capable`).
- Verificación manual: instalar en móvil, conectar altavoz Bluetooth, comprobar AVRCP.

**Estimación**: ~1 día.

---

## Fase 9 ⏳ — Editor de metadatos

**Objetivo**: superusuario edita los campos del archivo conservando la verdad externa intacta.

**Pre-requisitos**: fase 5 + endpoints PATCH (incluidos en esta fase).

**Entregables**:
- `api/items.py` extendido: `POST /api/items`, `PATCH /api/items/{id}`, `POST /api/items/from-url`.
- `api/songs.py` extendido: `POST /api/songs`.
- Validación contra JSON Schema (vía AJV en frontend) además de Pydantic en backend.
- `components/MetaForm.tsx` — formulario 2 columnas:
  - Izquierda: external (read-only, con timestamp de fetch + botón refetch — funcional en fase 11).
  - Derecha: campos editables con autocompletado de geo_id/song_id.
- "Crear nueva song" inline desde el form de item.
- Atajos teclado: Cmd+Enter publicar, Cmd+G focus geo, Tab entre campos.
- Status badge dinámico según `compute_status()`.

**Estimación**: ~2 días.

---

## Fase 10 ⏳ — Cola de triaje

**Objetivo**: procesar pendientes en lote.

**Pre-requisitos**: fase 9.

**Entregables**:
- `routes/Triage.tsx` — tabla con filtro por status / plataforma / CCAA.
- Drawer lateral para edición rápida sin perder el contexto de la lista.
- Bulk actions: marcar varios como `needs_review`, asignar el mismo `geo_id`, etc.
- Endpoint `POST /api/items/bulk-update`.

**Estimación**: ~1 día.

---

## Fase 11 ⏳ — Refetch externo + diff

**Objetivo**: detectar cambios en metadatos externos y mostrar el diff.

**Pre-requisitos**: fase 10 + integraciones (parcial).

**Entregables**:
- `POST /api/items/{id}/refetch` — vuelve a llamar la plataforma; si `raw_hash` cambia, status pasa a `needs_review` y se guarda el diff.
- `GET /api/items/{id}/external-diff` — diff humano-legible entre raw anterior y actual.
- Componente UI `ExternalDiff.tsx` para mostrar campos cambiados con highlight.

**Estimación**: ~0.5 días.

---

## Fase 12 ⏳ — Segmentos

**Objetivo**: dividir un media largo en varios items (caso medley).

**Pre-requisitos**: fase 9.

**Entregables**:
- `POST /api/items/{id}/segments` — crea item hermano con misma URL y nuevo segment.
- UI: botón "Añadir segmento" en el editor; validación de no-overlap opcional.
- Player respeta `offset_s`/`duration_s` (ya implementado en fase 6).

**Estimación**: ~0.5 días.

---

## Fase 13 ⏳ — Integración Spotify

**Objetivo**: pegar URL Spotify → metadatos pre-rellenados; reproducir en navegador (Premium) o embed.

**Pre-requisitos**: fase 9.

**Entregables**:
- `integrations/spotify.py`:
  - OAuth 2.0 Authorization Code + PKCE.
  - `GET /api/integrations/spotify/login` → redirect.
  - `GET /api/integrations/spotify/callback` → guarda refresh token cifrado.
  - `GET /api/integrations/spotify/token` → access token corto al frontend.
  - `GET /api/integrations/spotify/resolve?url=...` → metadata enriquecida.
- Frontend `integrations/spotify-playback.ts`:
  - **Embeds para todos** (sin login).
  - **Web Playback SDK** para usuarios Premium (login → device en MATOS).
- Entrada en `.env.example`: `SPOTIFY_CLIENT_ID`, `SPOTIFY_CLIENT_SECRET`, `SPOTIFY_REDIRECT_URI`.
- **Limitación documentada**: Web Playback SDK requiere Spotify Premium.

**Estimación**: ~2 días.

---

## Fase 14 ⏳ — Integración YouTube

**Objetivo**: pegar URL YouTube → metadatos + reproducción IFrame.

**Pre-requisitos**: fase 9.

**Entregables**:
- `integrations/youtube.py`:
  - oEmbed sin auth (title, author, thumbnail).
  - Opcional: YouTube Data API v3 con `YOUTUBE_API_KEY` (10k unidades/día gratis) → duración, descripción, fecha.
  - `GET /api/integrations/youtube/resolve?url=...`.
- Frontend `integrations/youtube-iframe.ts` con YouTube IFrame Player API.

**Estimación**: ~0.5 días.

---

## Fase 15 ⏳ — Integración Wikimedia/Wikidata

**Objetivo**: enlazar items a entidades Wikidata (preparación para futura exportación OAI-PMH a Europeana).

**Pre-requisitos**: fase 9.

**Entregables**:
- `integrations/wikimedia.py`:
  - Wikidata SPARQL endpoint para entidades.
  - Wikimedia Commons API para imágenes/audio CC.
- Campo opcional `wikidata_id` en `Item` (Q-id).
- UI: input con autocompletado SPARQL.

**Estimación**: ~0.5 días.

---

## Fase 16 ⏳ — CLI utilidades

**Objetivo**: comandos de terminal para tareas frecuentes (alternativa al UI editor).

**Pre-requisitos**: fase 2.

**Entregables**:
- `matos new-pueblo --ccaa X --provincia Y NombrePueblo` — crea estructura.
- `matos new-item <pueblo-path> <fichero|url>` — calcula sha256, genera UUID, escribe `meta.json` mínimo.
- `matos init` (refinado): scaffold completo con CCAA de ejemplo, gitignore en `archivo/`.
- Tests integración con filesystem temporal.

**Estimación**: ~1 día.

---

## Fase 17 ⏳ — Búsqueda + filtros

**Objetivo**: buscar a través del archivo por texto + filtros estructurados.

**Pre-requisitos**: fases 2-3.

**Entregables**:
- SQLite FTS5 sobre `title`, `enrichment.notes`, `tags`, `context.interprete`, `context.recopilador`.
- `GET /api/search?q=...&kind=...&status=...&geo=...&year_from=...&year_to=...`.
- Frontend: barra de búsqueda global + página `/search` con filtros laterales.

**Estimación**: ~1 día.

---

## Fase 18 ⏳ — Pulido + despliegue

**Objetivo**: producción-ready.

**Pre-requisitos**: todas las anteriores.

**Entregables**:
- Atajos teclado globales documentados.
- Accesibilidad ARIA en todos los componentes interactivos.
- Modo oscuro pulido (ya hay base en CSS).
- Importar CA Caddy en móvil — guía paso a paso.
- `scripts/tailscale-serve.sh` para acceso desde fuera de la LAN.
- Manual de usuario en `docs/USER_GUIDE.md`.
- Decisión de registry: GHCR / Docker Hub / local; configurar `make release`.
- (Opcional) Let's Encrypt real con dominio público.

**Estimación**: ~1.5 días.

---

## Cross-cutting (consistente en todas las fases)

- **Tests verdes antes de commit**: `make test` debe pasar.
- **Lint limpio**: `make lint` sin warnings; `make format` antes de commit si hay cambios.
- **Commits estructurados**: `feat: phase N — <título>` para cierre de fase; `fix:`, `refactor:`, `docs:`, `chore:` para intermedios.
- **Schema bumps**: cambios breaking en modelos Pydantic → bumpear `SCHEMA_VERSION` en `models/common.py` y documentar migración.
- **Hot reload no rompe**: en dev, los cambios en `backend/matos/` o `frontend/src/` deben recargar sin reiniciar contenedor.
- **Reproducibilidad cross-machine**: cualquier fase clonable + `make lock && make up` debe funcionar desde cero en macOS/Linux/Windows con solo Docker.

## Diferencias respecto a MNEMOSINE completo

MATOS es un **subconjunto compatible** del stack descrito en `arquitectura_archivo_etnomusicologico.md`:

| MATOS | MNEMOSINE completo (futuro) |
|---|---|
| SQLite (índice derivado del filesystem) | PostgreSQL 16 + PostGIS + ltree |
| Filesystem local | Garage S3 (casa) / Hetzner Object Storage (cloud) |
| Sin auth | FastAPI-Users → Keycloak |
| Sin app móvil nativa | React Native + Expo + react-native-track-player |
| Sin mapa | MapLibre GL JS + Martin sirviendo MVT |
| Sin Navidrome | Navidrome sidecar para clientes Subsonic |

La migración futura es una cuestión de añadir adaptadores (`StorageAdapter`, `IndexAdapter`) y comandos de export, no de reescribir.
