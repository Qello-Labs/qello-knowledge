from datetime import timedelta

from qello_knowledge.sources.clock import SystemClock


def test_system_clock_provides_aware_utc_and_monotonic_time():
    clock = SystemClock()
    before = clock.monotonic()
    clock.sleep(0)
    assert clock.monotonic() >= before
    assert clock.now().utcoffset() == timedelta(0)
