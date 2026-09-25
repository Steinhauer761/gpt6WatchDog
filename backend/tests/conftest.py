import pytest

from backend.app.abuse_guardrails import RATE_LIMITER


@pytest.fixture(autouse=True)
def reset_rate_limits():
    RATE_LIMITER.clear()
    yield
    RATE_LIMITER.clear()
