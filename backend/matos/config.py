"""Configuración global vía pydantic-settings (lee de env vars y `.env`)."""

from __future__ import annotations

from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="MATOS_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    env: str = "dev"
    domain: str = "matos.local"
    archive_path: Path = Path("/data/archivo")
    index_path: Path = Path("/data/index/matos.db")


settings = Settings()
