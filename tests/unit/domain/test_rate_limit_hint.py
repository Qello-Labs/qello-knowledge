from datetime import UTC, datetime

import pytest

from qello_knowledge.domain import source
from qello_knowledge.domain.source import SourceResponse, default_rate_limit_hint


@pytest.mark.parametrize(("header", "seconds"), [("30", 30.0), ("0", 0.0)])
def test_retry_after_seconds_are_preserved_without_reading_clock(header, seconds, monkeypatch):
    class NoClock(datetime):
        @classmethod
        def now(cls, tz=None):
            raise AssertionError("어댑터 힌트는 시계를 읽으면 안 된다")

    monkeypatch.setattr(source, "datetime", NoClock)
    hint = default_rate_limit_hint(SourceResponse(429, {"Retry-After": header}))
    assert hint.retry_after_seconds == seconds
    assert hint.retry_at is None
    assert hint.remaining == 0


def test_http_date_is_an_absolute_utc_time():
    hint = default_rate_limit_hint(SourceResponse(429, {"Retry-After": "Thu, 01 Jan 2026 00:00:30 GMT"}))
    assert hint.retry_at == datetime(2026, 1, 1, 0, 0, 30, tzinfo=UTC)
    assert hint.retry_after_seconds is None


@pytest.mark.parametrize("value", [None, "", "garbage", "-1", "nan", "inf", "9" * 400])
def test_missing_or_invalid_retry_after_has_no_hint(value):
    headers = {} if value is None else {"Retry-After": value}
    assert default_rate_limit_hint(SourceResponse(429, headers)) is None
