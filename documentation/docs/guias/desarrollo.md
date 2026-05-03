# Desarrollo

## Filosofía

!!! quote "Cero deps en el host"
    Salvo Docker + Make + Git, nada se instala en la máquina. Todo el
    desarrollo (Python, Node, uv, pnpm, tests, lint) corre en contenedores.

## Arrancar el dev

```bash
git clone <repo> MATOS
cd MATOS
cp .env.example .env
make lock        # 1ª vez
make up          # build + start
```

URLs:

- Backend API: <http://localhost:8000/api/health>
- Frontend (Vite): <http://localhost:5173>
- HTTPS interno: <https://localhost>
- Docs (este sitio): <http://localhost:8001>

## Editar código

Edita en tu IDE en el host. El bind mount + hot reload se ocupa del resto:

- **Backend**: uvicorn `--reload` detecta cambios en `backend/matos/`.
- **Frontend**: Vite HMR detecta cambios en `frontend/src/`.
- **Docs**: MkDocs `--dev-addr` recarga al guardar `documentation/docs/`.

## Workflow

1. **Crear rama** desde `main`.
2. **Implementar + tests** (`make test` debe quedar verde).
3. **Lint** (`make lint`); auto-fix con `make format`.
4. **Actualizar docs** si cambian APIs / esquemas / casos de uso.
5. **Si cambia `index/schema.sql`**: `make db-diagram` regenera el ER.
6. **Commit** con mensaje convencional (`feat:`, `fix:`, `docs:`…).
7. **Push** + merge a `main`.

## Reglas de oro

- :material-close-circle: **No** ejecutar `python`, `pytest`, `pip`, `uv`, `node`, `npm`, `pnpm` en el host.
- :material-close-circle: **No** comitear ficheros de audio/vídeo al repo principal.
- :material-close-circle: **No** escribir directamente sobre el SQLite de índice — siempre `make reindex`.
- :material-close-circle: **No** editar `external_metadata` a mano — solo via `POST /refetch`.
- :material-check-circle: **Sí** Pydantic v2 como fuente de verdad de schemas.
- :material-check-circle: **Sí** UUIDs estables: renombrar archivos no rompe relaciones.
- :material-check-circle: **Sí** SHA-256 obligatorio para items con fichero (lo calcula `make new-item`).
