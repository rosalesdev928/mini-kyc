"""The sliding-window limiter (pure logic, with a fake clock)."""

from app.core.rate_limit import SlidingWindowLimiter


class Clock:
    def __init__(self):
        self.now = 1000.0

    def __call__(self) -> float:
        return self.now


def test_allows_up_to_the_limit_then_blocks_with_a_wait_time():
    clock = Clock()
    limiter = SlidingWindowLimiter(3, 60, clock)
    assert [limiter.acquire("ip") for _ in range(3)] == [0.0, 0.0, 0.0]
    wait = limiter.acquire("ip")
    assert 0 < wait <= 60


def test_the_window_slides_so_old_events_stop_counting():
    clock = Clock()
    limiter = SlidingWindowLimiter(2, 60, clock)
    limiter.acquire("ip")
    limiter.acquire("ip")
    assert limiter.acquire("ip") > 0
    clock.now += 61
    assert limiter.acquire("ip") == 0.0


def test_each_key_has_its_own_budget():
    limiter = SlidingWindowLimiter(1, 60, Clock())
    assert limiter.acquire("a") == 0.0
    assert limiter.acquire("a") > 0
    assert limiter.acquire("b") == 0.0


def test_a_blocked_attempt_is_not_counted_so_the_wait_does_not_grow():
    clock = Clock()
    limiter = SlidingWindowLimiter(1, 60, clock)
    limiter.acquire("ip")
    first_wait = limiter.acquire("ip")
    clock.now += 10
    second_wait = limiter.acquire("ip")
    assert second_wait < first_wait


def test_failures_can_be_recorded_separately_and_cleared():
    limiter = SlidingWindowLimiter(2, 300, Clock())
    assert limiter.retry_after("ip") == 0.0
    limiter.record("ip")
    limiter.record("ip")
    assert limiter.retry_after("ip") > 0
    limiter.clear("ip")
    assert limiter.retry_after("ip") == 0.0


def test_a_limit_of_zero_disables_the_limiter():
    limiter = SlidingWindowLimiter(0, 60, Clock())
    assert all(limiter.acquire("ip") == 0.0 for _ in range(100))
    assert not limiter.enabled


def test_idle_keys_are_dropped_so_memory_stays_bounded():
    clock = Clock()
    limiter = SlidingWindowLimiter(1, 60, clock)
    limiter._MAX_KEYS = 5
    for index in range(5):
        limiter.record(f"ip-{index}")
    clock.now += 120
    limiter.record("fresh")
    assert set(limiter._events) == {"fresh"}
