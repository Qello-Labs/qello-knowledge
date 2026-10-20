from datetime import UTC, datetime

import pytest

from qello_knowledge.adapters.github import GitHubRepoFilesAdapter
from qello_knowledge.domain.source import FailureType, ResponseClass, ResponseOutcome, SourceResponse, default_classify


@pytest.mark.parametrize(
    "status,headers",
    [
        (403, {"x-ratelimit-remaining": "0"}),
        (429, {"x-ratelimit-remaining": "0"}),
        (403, {"retry-after": "60"}),
        (429, {"retry-after": "60"}),
    ],
)
def test_github_limits_are_transient(status, headers):
    assert GitHubRepoFilesAdapter().classify(SourceResponse(status, headers)) == ResponseClass(
        ResponseOutcome.TRANSIENT, FailureType.RATE_LIMITED
    )


@pytest.mark.parametrize("status", [200, 401, 403, 404, 500])
def test_other_classification_is_default(status):
    response = SourceResponse(status)
    assert GitHubRepoFilesAdapter().classify(response) == default_classify(response)


@pytest.mark.parametrize(
    "headers,remaining,seconds,absolute",
    [
        ({"retry-after": "60", "x-ratelimit-remaining": "100"}, 0, 60, None),
        ({"retry-after": "60", "x-ratelimit-remaining": "0", "x-ratelimit-reset": "1767225700"}, 0, 60, 1767225700),
        ({"x-ratelimit-remaining": "0", "x-ratelimit-reset": "1767225700"}, 0, None, 1767225700),
        ({"x-ratelimit-remaining": "10", "x-ratelimit-reset": "1767225700"}, 10, None, None),
        ({"x-ratelimit-remaining": "0", "x-ratelimit-reset": "bad"}, 0, None, None),
        ({"retry-after": "bad", "x-ratelimit-remaining": "2"}, 2, None, None),
        (
            {
                "retry-after": "Thu, 01 Jan 2026 00:01:00 GMT",
                "x-ratelimit-remaining": "0",
                "x-ratelimit-reset": "1767225700",
            },
            0,
            None,
            1767225700,
        ),
    ],
)
def test_rate_hint_normalization(headers, remaining, seconds, absolute):
    hint = GitHubRepoFilesAdapter().rate_limit_hint(SourceResponse(200, headers))
    assert hint.remaining == remaining and hint.retry_after_seconds == seconds
    assert hint.retry_at == (None if absolute is None else datetime.fromtimestamp(absolute, UTC))


@pytest.mark.parametrize(
    "headers", [{}, {"x-ratelimit-remaining": "bad"}, {"retry-after": "bad", "x-ratelimit-reset": "bad"}]
)
def test_no_valid_headers_means_no_hint(headers):
    assert GitHubRepoFilesAdapter().rate_limit_hint(SourceResponse(200, headers)) is None
