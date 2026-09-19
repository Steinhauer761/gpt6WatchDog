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


def mobile_headers() -> dict[str, str]:
    pair = client.post(
        "/v1/mobile/pair",
        headers=auth_headers(),
        json={"device_name": "CI Android"},
    )
    assert pair.status_code == 200, pair.text
    return {"Authorization": f"Bearer {pair.json()['token']}"}


def test_health_is_real_python_api():
    response = client.get("/health")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["python_backend"] is True
    assert "media-inspection" in body["features"]
    assert "research-search-web-tor-archive" in body["features"]
    assert "bounded-onion-crawl" in body["features"]
    assert "onion-address-discovery" in body["features"]
    assert "scam-reportability-score" in body["features"]
    assert "android-companion-pairing" in body["features"]
    assert "android-mobile-triage" in body["features"]


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


def test_mobile_pairing_issues_limited_scope_token():
    pair = client.post(
        "/v1/mobile/pair",
        headers=auth_headers(),
        json={"device_name": "Pixel companion"},
    )
    assert pair.status_code == 200, pair.text
    body = pair.json()
    assert body["scope"] == "watchdog-mobile"
    assert body["device_name"] == "Pixel companion"
    assert body["token"]


def test_mobile_token_can_triage_but_not_use_admin_only_tools():
    headers = mobile_headers()
    mobile_triage = client.post(
        "/v1/mobile/triage/text",
        headers=headers,
        json={"text": "https://example.com from 8.8.8.8"},
    )
    assert mobile_triage.status_code == 200, mobile_triage.text
    assert mobile_triage.json()["urls"] == ["https://example.com"]

    admin_only = client.post(
        "/v1/intel/ip",
        headers=headers,
        json={"ip": "8.8.8.8"},
    )
    assert admin_only.status_code == 401


def test_scam_triage_scores_reportability_without_accusing_number_owner():
    response = client.post(
        "/v1/scam/triage",
        headers=auth_headers(),
        json={
            "number": "+1 780 555 0101",
            "channel": "call",
            "claimed_identity": "CRA",
            "message": "Urgent. Pay with gift cards or your account will be suspended. Give us your verification code.",
            "repeat_count": 3,
            "unsolicited": True,
            "requested_money": True,
            "requested_credentials": True,
            "claimed_organization": True,
            "threat_or_urgency": True,
        },
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["score"] == 10
    assert body["disposition"] == "reportable"
    assert body["report_packet"]["automatic_submission"]["submitted"] is False
    assert "displayed number" in body["report_packet"]["important_note"].lower()
    assert len(body["evidence_sha256"]) == 64


def test_mobile_scam_triage_uses_same_scoring_engine():
    response = client.post(
        "/v1/mobile/scam/triage",
        headers=mobile_headers(),
        json={
            "number": "+17805550103",
            "channel": "sms",
            "message": "Urgent: send payment by gift card and give your verification code.",
            "unsolicited": True,
        },
    )
    assert response.status_code == 200, response.text
    assert response.json()["score"] >= 6


def test_scam_triage_uses_requested_scale():
    response = client.post(
        "/v1/scam/triage",
        headers=auth_headers(),
        json={"number": "+17805550102", "message": "Hello", "unsolicited": False},
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["score"] == 1
    assert body["disposition"] == "not_reportable"
    assert body["scale"]["5"] == "uncertain"


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


def test_onion_discovery_is_a_real_authenticated_endpoint(monkeypatch):
    async def fake_discovery(query: str, category: str, max_results: int):
        return {
            "query": query,
            "category": category,
            "result_count": 1,
            "results": [{
                "url": "http://abcdefghijklmnopqrstuvwxyz234567abcdefghijklmnopqrstuvwxyz2345.onion",
                "host": "abcdefghijklmnopqrstuvwxyz234567abcdefghijklmnopqrstuvwxyz2345.onion",
                "source_count": 2,
                "mention_count": 3,
                "sources": ["Reddit", "Ahmia public index"],
            }],
        }

    monkeypatch.setattr(main_module, "discover_onion_addresses", fake_discovery)
    response = client.post(
        "/v1/research/onion/discover",
        headers=auth_headers(),
        json={"query": "news", "category": "news", "max_results": 100},
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["category"] == "news"
    assert body["result_count"] == 1
    assert body["results"][0]["source_count"] == 2


def test_onion_discovery_requires_login():
    response = client.post(
        "/v1/research/onion/discover",
        json={"query": "news", "category": "news", "max_results": 10},
    )
    assert response.status_code == 401


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
