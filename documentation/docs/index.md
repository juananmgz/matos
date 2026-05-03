---
title: MATOS
---

# MATOS

Reproductor y catalogador del archivo de etnomusicología **MNEMOSINE**.

!!! info "Para qué sirve este sitio"
    Este es el **wiki interno de MATOS**: notas técnicas, decisiones de
    diseño, casos de uso, referencia de la API y diagramas. Vive en el
    repo (`documentation/docs/`), se versiona con git y se sirve localmente
    con `make docs`.

## Qué hace MATOS

- Navega el archivo por jerarquía **Comunidad Autónoma → Provincia → Pueblo**.
- Lista, reproduce y muestra metadatos de elementos: audio, vídeo, partitura,
  letra, y URLs externas (Spotify, YouTube, Wikimedia, Facebook…).
- Relaciona elementos: versiones de una misma canción, letra ↔ grabación,
  partitura ↔ grabación, intérprete/recopilador/lugar/año.
- Permite editar metadatos vía formularios validados por JSON Schema.
- Reproduce desde móvil con audio Bluetooth A2DP (vía Media Session API).

## Mapa del sitio

<div class="grid cards" markdown>

-   :material-database:{ .lg .middle } **[Arquitectura](arquitectura/index.md)**

    ---

    Stack, modelo de datos, esquema SQLite, capas de metadatos.

-   :material-api:{ .lg .middle } **[API](api/index.md)**

    ---

    Endpoints REST: tree, items, songs, streaming.

-   :material-book-open-variant:{ .lg .middle } **[Casos de uso](casos-de-uso/index.md)**

    ---

    Escenarios reales: Ringorrango — J#4, fieldwork, multi-canción.

-   :material-tools:{ .lg .middle } **[Guías](guias/desarrollo.md)**

    ---

    Cómo arrancar el dev, comandos `make`, flujo de trabajo.

</div>

## Estado de fases

| # | Fase | Estado |
|---|---|---|
| 0 | Scaffold + dockerización | :material-check-bold:{ .ok } |
| 1 | Schemas Pydantic | :material-check-bold:{ .ok } |
| 1.5 | Discos + huérfanas + artistas | :material-check-bold:{ .ok } |
| 2 | Storage + índice SQLite | :material-check-bold:{ .ok } |
| 3 | API lectura (tree, items, songs, discos) | :material-check-bold:{ .ok } |
| 4 | API streaming + URL resolution | :material-check-bold:{ .ok } |
| 5 | Frontend navegación | :material-clock-outline: pendiente |
| 6 | Player + Media Session API | :material-clock-outline: pendiente |
| … | … | … |

Plan completo en [`ROADMAP.md`](https://github.com/juananmgz/matos/blob/main/ROADMAP.md).
