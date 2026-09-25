from worker.rate_limit import FixedWindowRateLimiter


def test_worker_limiter_is_bounded_by_the_configured_window():
    now = [3_600.0]
    limiter = FixedWindowRateLimiter(clock=lambda: now[0])

    assert limiter.consume("crawl", "worker-secret", 1, 60).allowed is True
    blocked = limiter.consume("crawl", "worker-secret", 1, 60)
    assert blocked.allowed is False
    assert blocked.remaining == 0

    now[0] = 3_660.0
    assert limiter.consume("crawl", "worker-secret", 1, 60).allowed is True
