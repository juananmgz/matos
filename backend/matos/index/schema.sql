-- Esquema del índice SQLite de MATOS.
--
-- El SQLite es DERIVADO del filesystem `archivo/`. Se reconstruye con
-- `matos reindex`. Nunca se escribe a mano.
--
-- Diseño orientado a migración a Postgres + PostGIS (MNEMOSINE completo):
-- columnas y tipos se eligen para mapear directo a las tablas
-- `geo_unit` / `work` / `media_asset` del schema futuro.

PRAGMA foreign_keys = ON;
PRAGMA journal_mode = WAL;

-- ─── meta ─────────────────────────────────────────────────────────────────
-- Metadatos del índice (versión schema, fecha de build, contadores).

CREATE TABLE IF NOT EXISTS meta (
    key   TEXT PRIMARY KEY,
    value TEXT NOT NULL
);

-- ─── geo_unit ────────────────────────────────────────────────────────────
-- CCAA / Provincia / Pueblo. Jerarquía vía `parent_id` y `path` ltree-like.

CREATE TABLE IF NOT EXISTS geo_unit (
    id          TEXT PRIMARY KEY,             -- UUID
    level       TEXT NOT NULL CHECK (level IN ('ccaa','provincia','pueblo')),
    nombre      TEXT NOT NULL,
    parent_id   TEXT REFERENCES geo_unit(id) ON DELETE CASCADE,
    path        TEXT NOT NULL UNIQUE,         -- ej. 'andalucia.granada.pampaneira'
    slug        TEXT NOT NULL,                -- segmento ASCII de la carpeta
    codigo      TEXT,                         -- INE u otros, según level
    fs_path     TEXT NOT NULL UNIQUE,         -- ruta relativa al archivo (carpeta)
    extra_json  TEXT NOT NULL DEFAULT '{}'    -- comarca/subcomarca/centroid/notas
);

CREATE INDEX IF NOT EXISTS idx_geo_unit_level     ON geo_unit(level);
CREATE INDEX IF NOT EXISTS idx_geo_unit_parent    ON geo_unit(parent_id);
CREATE INDEX IF NOT EXISTS idx_geo_unit_path      ON geo_unit(path);

-- ─── song ────────────────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS song (
    id              TEXT PRIMARY KEY,         -- UUID
    title           TEXT NOT NULL,
    geo_id          TEXT REFERENCES geo_unit(id) ON DELETE SET NULL,
    title_variants  TEXT NOT NULL DEFAULT '[]',  -- JSON array
    tags            TEXT NOT NULL DEFAULT '[]',  -- JSON array
    notes           TEXT,
    fs_path         TEXT NOT NULL UNIQUE
);

CREATE INDEX IF NOT EXISTS idx_song_geo  ON song(geo_id);

-- ─── item ────────────────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS item (
    id                  TEXT PRIMARY KEY,     -- UUID
    kind                TEXT NOT NULL CHECK (kind IN ('audio','video','score','lyrics','url')),
    title               TEXT NOT NULL,
    file                TEXT,                 -- nombre fichero relativo al pueblo
    url                 TEXT,
    geo_id              TEXT REFERENCES geo_unit(id) ON DELETE SET NULL,
    song_id             TEXT REFERENCES song(id)     ON DELETE SET NULL,
    sha256              TEXT,
    mime_type           TEXT,
    duration_s          INTEGER,
    source_type         TEXT NOT NULL CHECK (source_type IN ('fieldwork','release','broadcast','derived')),
    enrichment_status   TEXT NOT NULL CHECK (enrichment_status IN ('pending','partial','complete','needs_review')),
    has_external        INTEGER NOT NULL DEFAULT 0,  -- 0/1
    platform            TEXT,                 -- spotify|youtube|… si aplica
    interpretes         TEXT NOT NULL DEFAULT '[]',  -- JSON array, denormalizado para FTS
    tags                TEXT NOT NULL DEFAULT '[]',
    segment_offset_s    INTEGER,
    segment_duration_s  INTEGER,
    raw_json            TEXT NOT NULL,        -- volcado completo del Item Pydantic (fuente de verdad para la API)
    created_at          TEXT NOT NULL,
    updated_at          TEXT,
    fs_path             TEXT NOT NULL UNIQUE  -- ruta del .meta.json
);

CREATE INDEX IF NOT EXISTS idx_item_geo       ON item(geo_id);
CREATE INDEX IF NOT EXISTS idx_item_song      ON item(song_id);
CREATE INDEX IF NOT EXISTS idx_item_kind      ON item(kind);
CREATE INDEX IF NOT EXISTS idx_item_status    ON item(enrichment_status);
CREATE INDEX IF NOT EXISTS idx_item_platform  ON item(platform);

-- ─── relation ────────────────────────────────────────────────────────────
-- Aristas dentro de un Song. Se reconstruyen por completo en cada reindex.

CREATE TABLE IF NOT EXISTS relation (
    id        INTEGER PRIMARY KEY AUTOINCREMENT,
    song_id   TEXT NOT NULL REFERENCES song(id) ON DELETE CASCADE,
    type      TEXT NOT NULL CHECK (type IN ('version_of','lyrics_of','score_of','cover_of','derived_from','same_as')),
    src_item  TEXT NOT NULL,
    tgt_item  TEXT NOT NULL,
    notes     TEXT
);

CREATE INDEX IF NOT EXISTS idx_relation_song  ON relation(song_id);
CREATE INDEX IF NOT EXISTS idx_relation_src   ON relation(src_item);
CREATE INDEX IF NOT EXISTS idx_relation_tgt   ON relation(tgt_item);

-- ─── FTS5: búsqueda de texto sobre item ──────────────────────────────────
-- Indexa título, intérpretes y tags. Se sincroniza vía triggers.

CREATE VIRTUAL TABLE IF NOT EXISTS item_fts USING fts5(
    title, interpretes, tags,
    content='item', content_rowid='rowid',
    tokenize='unicode61 remove_diacritics 2'
);

CREATE TRIGGER IF NOT EXISTS item_ai AFTER INSERT ON item BEGIN
    INSERT INTO item_fts(rowid, title, interpretes, tags)
    VALUES (new.rowid, new.title, new.interpretes, new.tags);
END;

CREATE TRIGGER IF NOT EXISTS item_ad AFTER DELETE ON item BEGIN
    INSERT INTO item_fts(item_fts, rowid, title, interpretes, tags)
    VALUES('delete', old.rowid, old.title, old.interpretes, old.tags);
END;

CREATE TRIGGER IF NOT EXISTS item_au AFTER UPDATE ON item BEGIN
    INSERT INTO item_fts(item_fts, rowid, title, interpretes, tags)
    VALUES('delete', old.rowid, old.title, old.interpretes, old.tags);
    INSERT INTO item_fts(rowid, title, interpretes, tags)
    VALUES (new.rowid, new.title, new.interpretes, new.tags);
END;

-- FTS sobre song (título + variantes).
CREATE VIRTUAL TABLE IF NOT EXISTS song_fts USING fts5(
    title, title_variants,
    content='song', content_rowid='rowid',
    tokenize='unicode61 remove_diacritics 2'
);

CREATE TRIGGER IF NOT EXISTS song_ai AFTER INSERT ON song BEGIN
    INSERT INTO song_fts(rowid, title, title_variants)
    VALUES (new.rowid, new.title, new.title_variants);
END;

CREATE TRIGGER IF NOT EXISTS song_ad AFTER DELETE ON song BEGIN
    INSERT INTO song_fts(song_fts, rowid, title, title_variants)
    VALUES('delete', old.rowid, old.title, old.title_variants);
END;

CREATE TRIGGER IF NOT EXISTS song_au AFTER UPDATE ON song BEGIN
    INSERT INTO song_fts(song_fts, rowid, title, title_variants)
    VALUES('delete', old.rowid, old.title, old.title_variants);
    INSERT INTO song_fts(rowid, title, title_variants)
    VALUES (new.rowid, new.title, new.title_variants);
END;
