"""Entry point FastAPI."""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from . import __version__
from .config import settings

app = FastAPI(
    title="MATOS",
    version=__version__,
    description="Reproductor del archivo de etnomusicología MNEMOSINE.",
)

# En dev el frontend Vite corre en :5173 y necesita CORS para llamar /api directo.
# En prod todo va por Caddy mismo origen → CORS innecesario pero no estorba.
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        f"https://{settings.domain}",
        "https://localhost",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/health")
def health() -> dict[str, str]:
    """Healthcheck — usado por Docker y por el frontend para verificar conexión."""
    return {
        "status": "ok",
        "version": __version__,
        "env": settings.env,
    }
