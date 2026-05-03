# MATOS

Reproductor y catalogador del archivo de etnomusicología **MNEMOSINE**.
Primera aplicación independiente del proyecto MNEMOSINE; diseñada para
integrarse con los módulos posteriores (mapa, app móvil, sidecar Navidrome)
sin reescritura.

Documento de arquitectura del sistema completo:
`../arquitectura_archivo_etnomusicologico.md` — leer para contexto. MATOS
implementa un subconjunto compatible: el mismo stack backend
(FastAPI/Pydantic) y el mismo modelo conceptual (`geo_unit` / `work` /
`media_asset`), sin Postgres ni S3 todavía.

## Qué hace MATOS

- Navega el archivo por jerarquía Comunidad Autónoma → Provincia → Pueblo.
- Lista, reproduce y muestra metadatos de elementos: audio, vídeo, partitura,
  letra, y URLs externas (Spotify, YouTube, Wikimedia, Facebook…).
- Relaciona elementos: versiones de una misma canción, letra ↔ grabación,
  partitura ↔ grabación, intérprete/recopilador/lugar/año, aparición en disco
  con timestamp.
- Permite editar metadatos vía formularios validados por JSON Schema.
- Reproduce desde móvil con audio Bluetooth A2DP (vía Media Session API) y
  Cast/AirPlay (vía Remote Playback API).

Fuera de alcance v0: mapa, autenticación multiusuario, app móvil nativa, S3.

## Stack

- **Backend**: FastAPI 0.115 + Python 3.12, Pydantic v2, SQLAlchemy 2.0
  (solo para SQLite de índice), uvicorn, typer (CLI).
- **Frontend**: React 18 + Vite + TypeScript, PWA-capable. Cliente API
  generado desde OpenAPI.
- **Datos**: filesystem (`archivo/`) como source-of-truth, JSON sidecars,
  índice SQLite regenerable con `make reindex`.
- **Player**: HTML5 `<audio>`/`<video>` + Media Session API; iframes para
  Spotify/YouTube embeds; Spotify Web Playback SDK opcional.
- **Despliegue**: Docker Compose. Caddy 2 como reverse proxy con HTTPS
  automático.

## Desarrollo 100% en contenedores

Único requisito en el host: Docker Engine + Compose v2 + Make.
**No instalar Python, Node, uv, ni pnpm en el host.** Todos los comandos
se ejecutan dentro de contenedores vía `make`.

Recomendado en macOS: OrbStack en vez de Docker Desktop (I/O 10× más rápido
sobre bind mounts).

```bash
git clone <repo> && cd MATOS
cp .env.example .env
make lock                               # primera vez: genera lock files
make up                                 # arranca dev
                                        #   backend  → http://localhost:8000
                                        #   frontend → http://localhost:5173
                                        #   https    → https://localhost (Caddy)
```

Edición de código: en el host con tu IDE favorito. Hot reload se dispara
dentro del contenedor (uvicorn `--reload` + Vite HMR).

`node_modules` y `.venv` viven en **volúmenes nombrados** Docker, no en bind
mount, para velocidad en Mac/Windows. `make clean` los borra (regeneran al
siguiente `make up`).

Para abrir el repo desde dentro del contenedor: VSCode/Cursor → "Reopen in
Container" (config en `.devcontainer/`).

## Layout del repositorio

```
MATOS/
├── backend/
│   ├── pyproject.toml
│   ├── uv.lock
│   ├── matos/
│   │   ├── main.py              # FastAPI app
│   │   ├── config.py            # settings (pydantic-settings)
│   │   ├── cli.py               # typer CLI
│   │   ├── models/              # Pydantic schemas (fase 1)
│   │   ├── storage/             # StorageAdapter — fase 2
│   │   ├── index/               # SQLite builder — fase 2
│   │   ├── api/                 # routers — fases 3-4
│   │   └── integrations/        # Spotify/YT/Wikimedia — fases 13-15
│   └── tests/
├── frontend/
│   ├── package.json
│   ├── vite.config.ts
│   └── src/
│       ├── main.tsx
│       ├── App.tsx
│       ├── routes/
│       ├── components/
│       └── integrations/        # spotify-playback, youtube-iframe, media-session
├── docker/
│   ├── backend.Dockerfile
│   ├── frontend.Dockerfile
│   ├── Caddyfile                # reverse proxy
│   └── Caddyfile.frontend       # serve estáticos en prod
├── scripts/                     # wrappers de docker compose
├── archivo/                     # datos (gitignored)
├── schemas/                     # JSON Schema generado desde Pydantic
├── docker-compose.yml           # base
├── docker-compose.override.yml  # dev (auto-cargado)
├── docker-compose.prod.yml      # prod
├── .devcontainer/
└── Makefile
```

## Modelo de datos (fase 1 en adelante)

Entidades principales:

1. **GeoUnit** (`_ccaa.json` / `_provincia.json` / `_pueblo.json` /
   `_huerfanas.json`). Carpeta = jerarquía. Campo `path` derivado del
   filesystem.
2. **Item** (`<uuid>.meta.json`). Una grabación, partitura, letra, o URL.
   Lleva `kind`, `geo_id`, opcionalmente `song_id`, `context` (intérprete,
   recopilador, fecha, lugar), `source` (fieldwork/release/broadcast/derived),
   `rights`, `external_metadata` (cache de plataforma), `enrichment` (status
   curacional), `segment` (sub-sección de un media más largo).
3. **Song** (`<uuid>.song.json`). Entidad lógica que agrupa items y declara
   relaciones (`version_of`, `lyrics_of`, `score_of`).
   `original_recording_missing=true` indica un stub creado desde un
   `TrackSegment` sin grabación de campo localizada.
4. **Artist** (`_artist.json`). Artista (solista, grupo u otro) con `slug`
   kebab-case, `geo_id` opcional, `aliases`, `bio`, `links`, `external_metadata`
   y `enrichment`. Vive en `archivo/artists/<slug>/`.
5. **Disco** (`_disco.json`) + **DiscoTrack** (`*.track.json`) +
   **TrackSegment** (embebido en track). Edición discográfica con tracks; cada
   track contiene 1+ segmentos que mapean tramos a `Song`s. `disco.artist_id`
   FK opcional → `artist`; resolución automática por convención de slug
   `discos/<slug>/...` ↔ `artists/<slug>/` cuando no se declara.

Identidad: UUIDs estables. Renombrar archivos no rompe relaciones.

Nombres de campos y enums se eligen para mapear directo a las tablas
`geo_unit` / `work` / `media_asset` del esquema Postgres descrito en el doc
de arquitectura.

### Layout del archivo

```
archivo/
├── _index.json                              # metadatos del archivo (versión schema)
├── geo/
│   ├── _huerfanas/                          # canciones sin CCAA conocida
│   │   ├── _huerfanas.json                  # opcional (UUID estable)
│   │   ├── songs/  └─ <uuid>.song.json
│   │   └── items/  └─ <uuid>.meta.json
│   ├── andalucia/
│   │   ├── _ccaa.json
│   │   ├── _huerfanas/                      # CCAA conocida, sin provincia
│   │   ├── granada/
│   │   │   ├── _provincia.json
│   │   │   ├── _huerfanas/                  # provincia conocida, sin pueblo
│   │   │   ├── pampaneira/
│   │   │   │   ├── _pueblo.json             # comarca, subcomarca, INE, geo
│   │   │   │   ├── items/
│   │   │   │   │   ├── 7f3a-…-romance.flac
│   │   │   │   │   ├── 7f3a-…-romance.meta.json
│   │   │   │   │   ├── 9b1c-…-letra.txt
│   │   │   │   │   └── 9b1c-…-letra.meta.json
│   │   │   │   └── songs/
│   │   │   │       └── <uuid>.song.json
├── artists/
│   └── <slug>/
│       └── _artist.json                     # artista (solista o grupo)
└── discos/
    └── <slug>/                              # mismo slug que artists/<slug>/
        └── (YYYY) <titulo-slug>/
            ├── _disco.json                  # FK opcional artist_id → artists/<slug>/
            ├── cover.jpg                    # opcional, ref por cover_file
            ├── 01-<track>.flac              # binarios al lado del _disco.json
            ├── 02-<track>.flac
            └── metadatos/
                ├── 01-<track>.track.json    # 1 por audio; declara segmentos
                └── 02-<track>.track.json
```

**Huérfanas** (`_huerfanas/`) puede vivir en cualquier nivel. Sirve para
canciones cuyo origen geográfico se conoce sólo parcialmente: a veces se
sabe la CCAA pero no la provincia, o la provincia pero no el pueblo (y la
canción no es común a toda la provincia). El `_huerfanas.json` es opcional:
si falta, el reindex sintetiza un UUID estable derivado del path.

**Discos** modela ediciones discográficas (LP/CD/EP/single/digital) de
folklore tradicional o folk moderno. Cada `*.track.json` describe un fichero
sonoro y declara N **segmentos** que mapean tramos del audio a `Song`s del
archivo geográfico. Bidireccionalidad disco↔geo:

- Si la canción tradicional ya existe en `geo/<...>/songs/`, el segmento la
  referencia vía `song_id`. La consulta inversa "qué tracks contienen esta
  Song" se resuelve por SQL contra `track_segment`.
- Si NO existe grabación de campo, se crea un `Song` *stub* en el nivel
  geográfico más fino conocido (pueblo, o `_huerfanas/` del nivel
  correspondiente) con `original_recording_missing=true`. El segmento apunta
  a ese stub. El stub no tiene Items propios.
- Si no se sabe nada del origen, el stub vive en `geo/_huerfanas/`.

`offset_s` y `duration_s` del segmento son ambos opcionales: sin offset,
empieza al inicio del track; sin duration, llega al final; sin ninguno,
el track entero es la canción.

## Modelo de metadatos externos vs. archivo

Items que vienen de plataformas externas mantienen DOS capas:

1. **`external_metadata`** — respuesta cruda de la plataforma. Solo se
   actualiza vía `POST /api/items/{id}/refetch`. **Nunca editar a mano**.
   Se conserva `raw_hash` (sha256) para detectar cambios.
2. **Campos top-level (`title`, `geo_id`, `song_id`, `context`, `rights`, …)**
   — verdad del archivo, editada por el superusuario. **Nunca se sobrescribe
   por refetch**.

`enrichment.status` se calcula automáticamente:
- `pending`: solo external, sin curación.
- `partial`: alguna curación, faltan campos requeridos.
- `complete`: todos los campos requeridos rellenos.
- `needs_review`: el external cambió desde última edición; revisar diff.

Reglas:
- El título legible del archivo va en `title`. El título tal-como-aparece-en-
  la-plataforma se preserva en `source.release.track_title_external`.
- `geo_id` es el origen geográfico de la canción, no la ubicación del artista.
- `context.interprete` puede coincidir con `source.release.artist` o no
  (recopilaciones, fieldwork reissues, etc. — campos distintos a propósito).
- Cuando un media externo contiene varias canciones, crear ítems hermanos con
  la misma `url` y distinto `segment.offset_s` / `segment.duration_s`.
- `enrichment.notes` es texto libre — documentar la lógica del enriquecimiento
  (códigos del artista, fuentes consultadas, contraste con otras grabaciones).

## Comandos

Todos vía `make` (ejecutan dentro de contenedores):

```bash
make help                               # lista comandos
make up                                 # arranca dev
make down                               # para
make logs s=backend                     # tail logs (s=servicio)
make shell                              # bash en backend
make test                               # pytest + vitest
make lint                               # ruff + eslint
make format                             # auto-format
make reindex                            # rebuild SQLite (≥ fase 2)
make validate                           # valida JSONs del archivo (≥ fase 1)
make new-pueblo args="--ccaa X --provincia Y NombrePueblo"
make new-item args="<pueblo-path> <fichero|url>"
make up-prod                            # imágenes de producción
make build                              # build con tag = git sha
make release                            # push a REGISTRY
make backup                             # tar archivo/ + dump índice
make clean                              # ⚠ borra volúmenes
```

## Acceso móvil (fase 8 en adelante)

Frontend es **PWA** instalable. Acceso desde el móvil:
- **LAN**: `https://matos.local` o IP del host (cert auto-firmado vía Caddy
  internal CA; importar CA al móvil una vez).
- **Fuera de LAN**: Tailscale (`make tailscale` en fase 18) — sin
  port-forwarding, cert válido automático.

Audio Bluetooth (A2DP): el SO enruta automáticamente. MATOS implementa
**Media Session API** completa para que los controles del altavoz/auriculares
(AVRCP play/pause/skip) funcionen.

## Integraciones externas (fases 13-15)

Configuración en `.env`:

```
SPOTIFY_CLIENT_ID=…
SPOTIFY_CLIENT_SECRET=…
SPOTIFY_REDIRECT_URI=https://matos.local/api/integrations/spotify/callback
YOUTUBE_API_KEY=…                       # opcional
```

- **Spotify**: OAuth PKCE, embeds para todos, Web Playback SDK para usuarios
  Premium. Resolución automática de metadata al pegar URL.
- **YouTube**: IFrame Player API (sin auth). Metadata vía oEmbed; con API key
  añade duración y fecha.
- **Wikimedia/Wikidata**: lectura libre. Permite enlazar items a entidades
  Wikidata (preparación para futura exportación OAI-PMH).

URL resolver: pegar URL → metadata pre-rellenada → guardar.

## Flujo de trabajo obligatorio al completar una fase

Al terminar cualquier fase (o cambio significativo):

1. **Tests verdes**: `make test` pasa sin errores.
2. **Commit en la rama de trabajo** con mensaje `feat: phase N — <título>`.
3. **Actualizar `README.md`**: estado de fases, comandos nuevos, estructura si cambia.
4. **Si cambia la estructura de la base de datos** (`index/schema.sql`,
   modelos Pydantic, layout `archivo/`, FKs, enums, reglas de resolución):

   **Toda la documentación que mencione la entidad afectada debe actualizarse en el mismo commit.**
   No basta con tocar `base-de-datos.md`: hay que auditar y actualizar al menos:

   - `documentation/db-schema.dot` — tablas, columnas y FKs.
   - `documentation/db-schema.png` — regenerar con `make db-diagram` y
     **sustituir** el fichero (path estable, referenciado desde docs y README).
     Se copia automáticamente a `documentation/docs/assets/db-schema.png`.
   - `documentation/docs/arquitectura/base-de-datos.md` — descripción de
     tablas, FKs, índices, reglas de resolución. Si añades una tabla nueva,
     intégrala en la sección correspondiente, no como apéndice.
   - `documentation/docs/arquitectura/index.md` — bloque "Layout del filesystem"
     si la entidad introduce carpetas nuevas.
   - `documentation/docs/arquitectura/modelo-metadatos.md` — si la entidad
     añade capas externo↔archivo o cambia las reglas de enriquecimiento.
   - `documentation/docs/api/index.md` — si la entidad expone endpoints
     nuevos o modifica los existentes.
   - `documentation/docs/casos-de-uso/*.md` — si algún caso queda
     desactualizado por el cambio.
   - `README.md` — estado de fases y árbol de carpetas si se altera.
   - `CLAUDE.md` — secciones "Modelo de datos", "Layout del archivo" y la
     tabla "Estado del proyecto".

   Antes de commitear, ejecutar:

   ```bash
   grep -rn "<nombre-entidad-vieja>" documentation/ README.md CLAUDE.md
   ```

   para detectar referencias rotas. Commitear todos los cambios juntos.
5. **Merge a `main`** desde el worktree principal:
   ```bash
   git -C /Users/juananmgz/Desktop/MNEMOSINE/MATOS merge --no-ff <rama> -m "Merge branch '<rama>'"
   git -C /Users/juananmgz/Desktop/MNEMOSINE/MATOS push origin main
   ```
6. **Actualizar estado** en la tabla de fases de este `CLAUDE.md` y en `ROADMAP.md`.

No dejar commits sin mergear a `main` al final de una sesión.

## Convenciones

- Pydantic v2 es la fuente de verdad de schemas; nunca editar `schemas/*.json`
  a mano. Se generan con `make export-schemas`.
- IDs UUID v4 generados por `make new-*`. Nunca renombrar a mano.
- SHA-256 obligatorio para items con fichero (lo calcula `make new-item`).
- Los media binarios pesados (>10 MB) viven fuera del repo git.
- El índice SQLite es **derivado**: nunca leer/escribir manualmente; reconstruir.
- Endpoints media usan HTTP Range para streaming (preparación para S3
  prefirmado en el futuro).
- Codificación de texto siempre UTF-8. Nombres de carpeta sin acentos
  (`andalucia`, no `Andalucía`); el campo `nombre` del JSON sí los lleva.

## Migración futura a MNEMOSINE completo

Cuando se incorporen Postgres+PostGIS y S3:
1. `matos export postgres` → SQL de inserción a `geo_unit` / `work` /
   `media_asset` (los campos ya están alineados).
2. `matos export s3 --bucket …` → sube ficheros y reescribe `storage_uri`.
3. `StorageAdapter` cambia de `LocalStorage` a `S3Storage`; resto sin tocar.

## No hacer

- No introducir Postgres, auth, ni S3 en v0.
- No usar MongoDB ni un CMS de patrimonio (ver doc de arquitectura, sección 1).
- No comitear ficheros de audio/vídeo al repo principal.
- No escribir directamente sobre el SQLite de índice.
- No ejecutar `python`, `pytest`, `pip`, `uv`, `node`, `npm`, `pnpm` en el host.
  Todo va vía `make`.
- No instalar dependencias modificando `pyproject.toml` o `package.json` desde
  el host sin reconstruir la imagen: `make shell` y trabajar dentro, o
  `make build` tras editar el manifest.
- No comitear `.venv/` ni `node_modules/` (gitignore ya los cubre).
- No correr el backend ni el frontend en el host en producción — siempre Docker.
- No hardcodear secretos; siempre `.env` montado o Docker secrets.
- No exponer el puerto del backend directamente; siempre tras Caddy en prod.
- No asumir que A2DP necesita código especial: implementar Media Session bien
  y el SO se ocupa.
- No editar `external_metadata` de items a mano: solo via `POST /refetch`.

## Estado del proyecto

| Fase | Estado |
|---|---|
| 0  Scaffold + docker | ✅ completada |
| 1  Schemas Pydantic | ✅ completada |
| 1.5 Discos + huérfanas + artistas (layout `geo/` + `discos/` + `artists/`) | ✅ completada |
| 2  Storage + índice SQLite | ✅ completada |
| 3  API lectura | ✅ completada |
| 4  API streaming | ✅ completada |
| 5  Frontend navegación | ⏳ |
| 6  Player + Media Session | ⏳ |
| 7  Vista Song | ⏳ |
| 8  PWA + móvil | ⏳ |
| 9  Editor metadatos | ⏳ |
| 10 Cola triaje | ⏳ |
| 11 Refetch + diff | ⏳ |
| 12 Segmentos | ⏳ |
| 13 Spotify | ⏳ |
| 14 YouTube | ⏳ |
| 15 Wikimedia/Wikidata | ⏳ |
| 16 CLI utilidades | ⏳ |
| 17 Búsqueda + filtros | ⏳ |
| 18 Pulido + despliegue | ⏳ |
