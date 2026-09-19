from io import BytesIO

from fastapi.testclient import TestClient
from PIL import Image

import backend.app.main as main_module
from backend.app.main import app

client = TestClient(app)


def auth_headers() -> dict[str, str]:
    response = client.post("/v1/auth/login", json={"password": "ci-password"})
    assert response.status_code == 200, response.text
    return {"Authorization": f"Bearer {response.json()['token']}"}


def test_health_is_real_python_api():
    response = client.get("/health")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["python_backend"] is True
    assert "media-inspection" in body["features"]
    assert "research-search-web-tor-archive" in body["features"]
    assert "bounded-onion-crawl" in body["features"]


def test_triage_requires_login_and_extracts_indicators():
    unauthorized = client.post("/v1/triage/text", json={"text": "https://example.com"})
    assert unauthorized.status_code == 401

    response = client.post(
        "/v1/triage/text",
        headers=auth_headers(),
        json={"text": "Contact test@example.com and inspect https://example.com from 8.8.8.8"},
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["emails"] == ["test@example.com"]
    assert body["urls"] == ["https://example.com"]
    assert body["ipv4"] == ["8.8.8.8"]
    assert len(body["sha256"]) == 64


def test_media_inspection_hashes_and_reads_image_dimensions():
    image_bytes = BytesIO()
    Image.new("RGB", (3, 2)).save(image_bytes, format="PNG")

    response = client.post(
        "/v1/media/inspect",
        headers=auth_headers(),
        files={"file": ("sample.png", image_bytes.getvalue(), "image/png")},
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["filename"] == "sample.png"
    assert len(body["sha256"]) == 64
    assert body["image"]["format"] == "PNG"
    assert body["image"]["width"] == 3
    assert body["image"]["height"] == 2


def test_research_search_is_a_real_authenticated_endpoint(monkeypatch):
    async def fake_search(query: str, scope: str, max_results: int):
        return {"query": query, "scope": scope, "result_count": 1, "results": [{"title": "Example", "url": "https://example.com", "surface": "web"}]}

    monkeypatch.setattr(main_module, "search_research_sources", fake_search)
    response = client.post(
        "/v1/research/search",
        headers=auth_headers(),
        json={"query": "public records", "scope": "both", "max_results": 5},
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["query"] == "public records"
    assert body["result_count"] == 1


def test_onion_crawler_rejects_non_onion_urls():
    response = client.post(
        "/v1/research/onion/crawl",
        headers=auth_headers(),
        json={"url": "https://example.com", "max_pages": 2, "max_depth": 0},
    )
    assert response.status_code == 400


def test_web_probe_rejects_private_targets_before_connecting():
    response = client.post(
        "/v1/probe/web-security",
        headers=auth_headers(),
        json={"url": "http://127.0.0.1", "authorization_confirmed": True},
    )
    assert response.status_code == 400
