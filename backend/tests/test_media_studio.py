from pathlib import Path
import tempfile

from fastapi.testclient import TestClient

import backend.app.media_routes as media_routes
from backend.app.main import app

client = TestClient(app)


def auth_headers() -> dict[str, str]:
    response = client.post("/v1/auth/login", json={"password": "ci-password"})
    assert response.status_code == 200, response.text
    return {"Authorization": f"Bearer {response.json()['token']}"}


def test_media_search_requires_login():
    response = client.get("/v1/media/search", params={"q": "rain", "kind": "video"})
    assert response.status_code == 401


def test_media_search_returns_real_source_shape(monkeypatch):
    async def fake_search(query: str, kind: str, limit: int):
        return {
            "query": query,
            "kind": kind,
            "count": 1,
            "results": [{
                "id": "commons:1",
                "source": "Wikimedia Commons",
                "title": "Rain clip",
                "kind": kind,
                "source_url": "https://commons.wikimedia.org/wiki/File:Rain.webm",
                "direct_url": "https://upload.wikimedia.org/example.webm",
                "license": "CC BY 4.0",
            }],
            "rights_note": "Verify rights before publishing.",
        }

    monkeypatch.setattr(media_routes, "search_open_media", fake_search)
    response = client.get(
        "/v1/media/search",
        headers=auth_headers(),
        params={"q": "rain", "kind": "video", "limit": 5},
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["count"] == 1
    assert body["results"][0]["source"] == "Wikimedia Commons"
    assert body["results"][0]["license"] == "CC BY 4.0"


def test_media_render_returns_mp4(monkeypatch):
    async def fake_render(**kwargs):
        work_dir = Path(tempfile.mkdtemp(prefix="watchdog-test-render-"))
        output = work_dir / "watchdog-edit.mp4"
        output.write_bytes(b"fake-mp4")
        return output, work_dir

    monkeypatch.setattr(media_routes, "render_basic_video", fake_render)
    response = client.post(
        "/v1/media/render",
        headers=auth_headers(),
        files={"video": ("clip.mp4", b"input-video", "video/mp4")},
        data={
            "start_seconds": "0",
            "end_seconds": "0",
            "aspect": "9:16",
            "speed": "1",
            "caption": "Test caption",
            "music_volume": "0.8",
        },
    )
    assert response.status_code == 200, response.text
    assert response.headers["content-type"].startswith("video/mp4")
    assert response.content == b"fake-mp4"
