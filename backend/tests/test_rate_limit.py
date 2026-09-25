from fastapi.testclient import TestClient

from backend.app.main import app
from backend.app.rate_limit import FixedWindowRateLimiter


client = TestClient(app)


def test_fixed_window_limiter_blocks_and_resets():
    now = [100.0]
    limiter = FixedWindowRateLimiter(clock=lambda: now[0])

    first = limiter.consume("test", "private-identity", 2, 60)
    second = limiter.consume("test", "private-identity", 2, 60)
    blocked = limiter.consume("test", "private-identity", 2, 60)

    assert first.allowed is True
    assert second.remaining == 0
    assert blocked.allowed is False
    assert blocked.retry_after == 20

    now[0] = 120.0
    reset = limiter.consume("test", "private-identity", 2, 60)
    assert reset.allowed is True
    assert reset.remaining == 1


def test_login_returns_429_with_retry_headers_after_ten_attempts():
    for _ in range(10):
        response = client.post("/v1/auth/login", json={"password": "wrong-password"})
        assert response.status_code == 401

    blocked = client.post("/v1/auth/login", json={"password": "wrong-password"})
    assert blocked.status_code == 429
    assert blocked.json()["error"] == "rate_limit_exceeded"
    assert int(blocked.headers["retry-after"]) > 0
    assert blocked.headers["ratelimit-remaining"] == "0"


def test_health_reports_guardrails_and_ai_remains_off():
    response = client.get("/health")
    assert response.status_code == 200
    body = response.json()
    assert body["abuse_guardrails"]["enabled"] is True
    assert body["abuse_guardrails"]["ai_limit"] == "5 requests per minute; 30 per day"
    assert body["ai_enabled"] is False


def test_disabled_ai_makes_no_billable_call_and_still_has_a_burst_cap():
    login = client.post("/v1/auth/login", json={"password": "ci-password"})
    assert login.status_code == 200
    headers = {"Authorization": f"Bearer {login.json()['token']}"}

    for _ in range(5):
        response = client.post("/v1/assistant", headers=headers, json={"message": "hello"})
        assert response.status_code == 503
        assert "switched off" in response.json()["detail"].lower()

    blocked = client.post("/v1/assistant", headers=headers, json={"message": "hello"})
    assert blocked.status_code == 429
    assert blocked.json()["error"] == "rate_limit_exceeded"
