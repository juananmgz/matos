"""Tests de la API de lectura (fase 3).

Reusa los fixtures de `test_index_builder` para construir un archivo de
juguete + índice SQLite, e inyecta su path vía `dependency_overrides`.
"""

from __future__ import annotations

from pathlib import Path
from uuid import UUID

import pytest
from fastapi.testclient import TestClient

from matos.api.deps import get_db_path
from matos.index import build_index
from matos.main import app
from matos.storage import LocalStorage

# Reusa fixtures
from .test_index_builder import (  # noqa: F401
    archive_with_disco_and_huerfanas,
    sample_archive,
)


@pytest.fixture
def client_with_db(
    archive_with_disco_and_huerfanas: tuple[Path, dict[str, UUID]],
    tmp_path: Path,
) -> tuple[TestClient, dict[str, UUID]]:
    root, ids = archive_with_disco_and_huerfanas
    db = tmp_path / "matos.db"
    report = build_index(LocalStorage(root), db)
    assert report.ok, report.errors

    app.dependency_overrides[get_db_path] = lambda: db
    try:
        yield TestClient(app), ids
    finally:
        app.dependency_overrides.clear()


# ─── tree ────────────────────────────────────────────────────────────────


class TestTree:
    def test_get_tree_nested(self, client_with_db) -> None:
        client, _ = client_with_db
        r = client.get("/api/tree")
        assert r.status_code == 200
        roots = r.json()
        ccaa = [n for n in roots if n["level"] == "ccaa"]
        assert len(ccaa) == 1
        assert ccaa[0]["nombre"] == "Andalucía"
        provincia = ccaa[0]["children"][0]
        assert provincia["level"] == "provincia"
        levels = {c["level"] for c in provincia["children"]}
        assert {"pueblo", "huerfanas"} <= levels

    def test_get_geo_unit_with_items_and_songs(self, client_with_db) -> None:
        client, ids = client_with_db
        r = client.get(f"/api/geo/{ids['pueblo']}")
        assert r.status_code == 200
        body = r.json()
        assert body["nombre"] == "Pampaneira"
        assert len(body["items"]) == 2
        assert len(body["songs"]) == 1
        assert body["songs"][0]["title"] == "Romance de la Loba"

    def test_get_geo_unit_include_filter(self, client_with_db) -> None:
        client, ids = client_with_db
        r = client.get(f"/api/geo/{ids['pueblo']}?include=children")
        body = r.json()
        assert "items" not in body
        assert "songs" not in body
        assert body["children"] == []

    def test_get_geo_by_path(self, client_with_db) -> None:
        client, _ = client_with_db
        r = client.get("/api/geo/by-path", params={"path": "andalucia.granada.pampaneira"})
        assert r.status_code == 200
        assert r.json()["nombre"] == "Pampaneira"

    def test_get_geo_unknown_404(self, client_with_db) -> None:
        client, _ = client_with_db
        r = client.get("/api/geo/00000000-0000-0000-0000-000000000000")
        assert r.status_code == 404


# ─── items ───────────────────────────────────────────────────────────────


class TestItems:
    def test_list_items_default(self, client_with_db) -> None:
        client, _ = client_with_db
        r = client.get("/api/items")
        assert r.status_code == 200
        body = r.json()
        assert body["total"] == 2
        assert body["limit"] == 50
        assert body["offset"] == 0
        assert {it["kind"] for it in body["items"]} == {"audio", "url"}

    def test_filter_by_kind(self, client_with_db) -> None:
        client, _ = client_with_db
        r = client.get("/api/items", params={"kind": "audio"})
        body = r.json()
        assert body["total"] == 1
        assert body["items"][0]["kind"] == "audio"

    def test_filter_by_geo_and_song(self, client_with_db) -> None:
        client, ids = client_with_db
        r = client.get("/api/items", params={"song_id": str(ids["song"])})
        assert r.json()["total"] == 2
        r = client.get("/api/items", params={"geo_id": str(ids["pueblo"])})
        assert r.json()["total"] == 2

    def test_pagination(self, client_with_db) -> None:
        client, _ = client_with_db
        r = client.get("/api/items", params={"limit": 1, "offset": 0})
        body = r.json()
        assert body["total"] == 2
        assert len(body["items"]) == 1
        r2 = client.get("/api/items", params={"limit": 1, "offset": 1})
        body2 = r2.json()
        assert len(body2["items"]) == 1
        assert body["items"][0]["id"] != body2["items"][0]["id"]

    def test_search_q_fts(self, client_with_db) -> None:
        client, _ = client_with_db
        r = client.get("/api/items", params={"q": "loba"})
        assert r.json()["total"] >= 1

    def test_get_item_detail(self, client_with_db) -> None:
        client, ids = client_with_db
        r = client.get(f"/api/items/{ids['audio']}")
        assert r.status_code == 200
        body = r.json()
        assert body["title"] == "Romance de la Loba"
        assert body["raw"]["title"] == "Romance de la Loba"

    def test_get_item_404(self, client_with_db) -> None:
        client, _ = client_with_db
        r = client.get("/api/items/00000000-0000-0000-0000-000000000000")
        assert r.status_code == 404

    def test_invalid_kind_422(self, client_with_db) -> None:
        client, _ = client_with_db
        r = client.get("/api/items", params={"kind": "bogus"})
        assert r.status_code == 422


# ─── songs ───────────────────────────────────────────────────────────────


class TestSongs:
    def test_list_songs(self, client_with_db) -> None:
        client, _ = client_with_db
        r = client.get("/api/songs")
        body = r.json()
        # 1 normal + 1 stub huérfana
        assert body["total"] == 2

    def test_filter_missing_recording(self, client_with_db) -> None:
        client, _ = client_with_db
        r = client.get("/api/songs", params={"original_recording_missing": True})
        body = r.json()
        assert body["total"] == 1
        assert body["items"][0]["original_recording_missing"] is True

    def test_get_song_with_items_and_disco_segments(self, client_with_db) -> None:
        client, ids = client_with_db
        r = client.get(f"/api/songs/{ids['song']}")
        assert r.status_code == 200
        body = r.json()
        assert body["title"] == "Romance de la Loba"
        assert len(body["items"]) == 2
        assert len(body["relations"]) == 1
        # 2 segmentos en discos referencian esta song
        assert len(body["disco_segments"]) == 2

    def test_get_song_404(self, client_with_db) -> None:
        client, _ = client_with_db
        r = client.get("/api/songs/00000000-0000-0000-0000-000000000000")
        assert r.status_code == 404


# ─── discos ──────────────────────────────────────────────────────────────


class TestDiscos:
    def test_list_discos(self, client_with_db) -> None:
        client, _ = client_with_db
        r = client.get("/api/discos")
        body = r.json()
        assert body["total"] == 1
        assert body["items"][0]["artista"] == "Ringorrango"

    def test_get_disco_with_tracks_and_segments(self, client_with_db) -> None:
        client, ids = client_with_db
        r = client.get(f"/api/discos/{ids['disco']}")
        assert r.status_code == 200
        body = r.json()
        assert len(body["tracks"]) == 2
        track2 = next(t for t in body["tracks"] if t["track_no"] == 2)
        assert len(track2["segments"]) == 2

    def test_get_disco_tracks_endpoint(self, client_with_db) -> None:
        client, ids = client_with_db
        r = client.get(f"/api/discos/{ids['disco']}/tracks")
        assert r.status_code == 200
        assert len(r.json()) == 2

    def test_track_segments_endpoint(self, client_with_db) -> None:
        client, ids = client_with_db
        r = client.get(f"/api/tracks/{ids['track2']}/segments")
        assert r.status_code == 200
        assert len(r.json()) == 2

    def test_get_disco_404(self, client_with_db) -> None:
        client, _ = client_with_db
        r = client.get("/api/discos/00000000-0000-0000-0000-000000000000")
        assert r.status_code == 404


# ─── infraestructura ─────────────────────────────────────────────────────


def test_missing_index_returns_503(tmp_path: Path) -> None:
    app.dependency_overrides[get_db_path] = lambda: tmp_path / "no-existe.db"
    try:
        client = TestClient(app)
        r = client.get("/api/tree")
        assert r.status_code == 503
        assert "reindex" in r.json()["detail"]
    finally:
        app.dependency_overrides.clear()


def test_openapi_schema_exposed() -> None:
    client = TestClient(app)
    r = client.get("/openapi.json")
    assert r.status_code == 200
    paths = r.json()["paths"]
    for p in [
        "/api/tree",
        "/api/items",
        "/api/items/{item_id}",
        "/api/songs",
        "/api/songs/{song_id}",
        "/api/discos",
        "/api/discos/{disco_id}",
    ]:
        assert p in paths, f"falta {p} en OpenAPI"
