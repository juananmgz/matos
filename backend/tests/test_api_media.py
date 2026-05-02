"""Tests del streaming + URL resolution (fase 4).

Verifica:
- HTTP Range parsing y respuestas 200/206/416.
- 400 para items URL en /api/media.
- Embed resolver: Spotify, YouTube, otros.
- Track de disco con su propio binario.
"""

from __future__ import annotations

from pathlib import Path
from uuid import UUID

import pytest
from fastapi.testclient import TestClient

from matos.api.deps import get_archive_root, get_db_path
from matos.api.media import resolve_embed
from matos.index import build_index
from matos.main import app
from matos.storage import LocalStorage

# Fixtures provistos vía `conftest.py`.


@pytest.fixture
def client_media(
    archive_with_disco_and_huerfanas: tuple[Path, dict[str, UUID]],
    tmp_path: Path,
) -> tuple[TestClient, dict[str, UUID], Path]:
    root, ids = archive_with_disco_and_huerfanas
    db = tmp_path / "matos.db"
    report = build_index(LocalStorage(root), db)
    assert report.ok, report.errors

    app.dependency_overrides[get_db_path] = lambda: db
    app.dependency_overrides[get_archive_root] = lambda: root
    try:
        yield TestClient(app), ids, root
    finally:
        app.dependency_overrides.clear()


# ─── Embed resolver (unit) ───────────────────────────────────────────────


class TestResolveEmbed:
    def test_spotify_track(self) -> None:
        out = resolve_embed("https://open.spotify.com/track/4iV5W9uYEdYUVa79Axb7Rh")
        assert out["platform"] == "spotify"
        assert out["type"] == "iframe"
        assert out["embed_url"] == "https://open.spotify.com/embed/track/4iV5W9uYEdYUVa79Axb7Rh"
        assert out["external_id"] == "4iV5W9uYEdYUVa79Axb7Rh"

    def test_spotify_track_with_locale(self) -> None:
        out = resolve_embed("https://open.spotify.com/intl-es/track/4iV5W9uYEdYUVa79Axb7Rh")
        assert out["platform"] == "spotify"
        assert "/embed/track/4iV5W9uYEdYUVa79Axb7Rh" in out["embed_url"]

    def test_spotify_album(self) -> None:
        out = resolve_embed("https://open.spotify.com/album/1DFixLWuPkv3KT3TnV35m3")
        assert "embed/album/" in out["embed_url"]

    def test_youtube_watch(self) -> None:
        out = resolve_embed("https://www.youtube.com/watch?v=dQw4w9WgXcQ")
        assert out["platform"] == "youtube"
        assert out["embed_url"] == "https://www.youtube.com/embed/dQw4w9WgXcQ"

    def test_youtube_watch_with_extra_params(self) -> None:
        out = resolve_embed("https://www.youtube.com/watch?list=ABC&v=dQw4w9WgXcQ&t=30")
        assert out["platform"] == "youtube"
        assert out["external_id"] == "dQw4w9WgXcQ"

    def test_youtu_be(self) -> None:
        out = resolve_embed("https://youtu.be/dQw4w9WgXcQ")
        assert out["platform"] == "youtube"
        assert out["embed_url"] == "https://www.youtube.com/embed/dQw4w9WgXcQ"

    def test_unknown_url_returns_link(self) -> None:
        out = resolve_embed("https://example.com/letra.txt")
        assert out["type"] == "link"
        assert out["platform"] == "other"
        assert "embed_url" not in out


# ─── Streaming local ─────────────────────────────────────────────────────


class TestStreamItem:
    def test_full_get_returns_200_with_body(self, client_media) -> None:
        client, ids, _ = client_media
        r = client.get(f"/api/media/{ids['audio']}")
        assert r.status_code == 200
        assert r.content == b"FLAC-FAKE-PAYLOAD"
        assert r.headers["accept-ranges"] == "bytes"
        assert r.headers["content-length"] == str(len(b"FLAC-FAKE-PAYLOAD"))

    def test_range_returns_206_partial(self, client_media) -> None:
        client, ids, _ = client_media
        r = client.get(
            f"/api/media/{ids['audio']}",
            headers={"Range": "bytes=0-3"},
        )
        assert r.status_code == 206
        assert r.content == b"FLAC"
        assert r.headers["content-range"] == "bytes 0-3/17"
        assert r.headers["content-length"] == "4"

    def test_range_open_ended(self, client_media) -> None:
        client, ids, _ = client_media
        r = client.get(
            f"/api/media/{ids['audio']}",
            headers={"Range": "bytes=5-"},
        )
        assert r.status_code == 206
        assert r.content == b"FAKE-PAYLOAD"
        assert r.headers["content-range"] == "bytes 5-16/17"

    def test_range_suffix(self, client_media) -> None:
        client, ids, _ = client_media
        r = client.get(
            f"/api/media/{ids['audio']}",
            headers={"Range": "bytes=-7"},
        )
        assert r.status_code == 206
        assert r.content == b"PAYLOAD"

    def test_range_out_of_bounds_returns_416(self, client_media) -> None:
        client, ids, _ = client_media
        r = client.get(
            f"/api/media/{ids['audio']}",
            headers={"Range": "bytes=999-"},
        )
        assert r.status_code == 416
        assert r.headers["content-range"] == "bytes */17"

    def test_url_item_returns_400(self, client_media) -> None:
        client, ids, _ = client_media
        r = client.get(f"/api/media/{ids['lyrics']}")
        assert r.status_code == 400
        assert "embed" in r.json()["detail"].lower()

    def test_unknown_id_returns_404(self, client_media) -> None:
        client, _, _ = client_media
        r = client.get("/api/media/00000000-0000-0000-0000-000000000000")
        assert r.status_code == 404


# ─── Embed endpoint ──────────────────────────────────────────────────────


class TestEmbedEndpoint:
    def test_url_item_returns_link(self, client_media) -> None:
        # lyrics url = https://example.com/letra.txt → link
        client, ids, _ = client_media
        r = client.get(f"/api/media/{ids['lyrics']}/embed")
        assert r.status_code == 200
        body = r.json()
        assert body["type"] == "link"
        assert body["platform"] == "other"
        assert body["original_url"] == "https://example.com/letra.txt"

    def test_local_item_returns_400(self, client_media) -> None:
        # audio sin url → no embed
        client, ids, _ = client_media
        r = client.get(f"/api/media/{ids['audio']}/embed")
        assert r.status_code == 400

    def test_unknown_id_returns_404(self, client_media) -> None:
        client, _, _ = client_media
        r = client.get("/api/media/00000000-0000-0000-0000-000000000000/embed")
        assert r.status_code == 404


# ─── Disco track streaming ───────────────────────────────────────────────


class TestStreamDiscoTrack:
    def test_full_get(self, client_media) -> None:
        client, ids, _ = client_media
        r = client.get(f"/api/media/disco-track/{ids['track1']}")
        assert r.status_code == 200
        assert r.content == b"FAKE-01"

    def test_range(self, client_media) -> None:
        client, ids, _ = client_media
        r = client.get(
            f"/api/media/disco-track/{ids['track2']}",
            headers={"Range": "bytes=0-3"},
        )
        assert r.status_code == 206
        assert r.content == b"FAKE"

    def test_unknown_track_404(self, client_media) -> None:
        client, _, _ = client_media
        r = client.get("/api/media/disco-track/00000000-0000-0000-0000-000000000000")
        assert r.status_code == 404
