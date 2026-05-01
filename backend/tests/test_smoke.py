"""Smoke tests — verifican que el scaffold básico arranca."""

from __future__ import annotations

from fastapi.testclient import TestClient

from matos import __version__
from matos.main import app


def test_health_endpoint() -> None:
    client = TestClient(app)
    r = client.get("/api/health")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "ok"
    assert body["version"] == __version__
    assert "env" in body


def test_version_constant() -> None:
    assert __version__ == "0.1.0"
