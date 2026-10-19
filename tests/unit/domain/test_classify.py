import pytest

from qello_knowledge.domain.source import (
    FailureType,
    ResponseOutcome,
    SourceResponse,
    TransportError,
    default_classify,
)


@pytest.mark.parametrize(
    ("status", "outcome", "failure"),
    [
        (200, "OK", None),
        (204, "OK", None),
        (299, "OK", None),
        (429, "TRANSIENT", "RATE_LIMITED"),
        (500, "TRANSIENT", "SERVER_ERROR"),
        (502, "TRANSIENT", "SERVER_ERROR"),
        (503, "TRANSIENT", "SERVER_ERROR"),
        (504, "TRANSIENT", "SERVER_ERROR"),
        (401, "AUTH", "AUTH_FAILED"),
        (403, "PERMANENT", "ACCESS_DENIED"),
        (404, "PERMANENT", "NOT_FOUND"),
        (410, "PERMANENT", "NOT_FOUND"),
        (400, "PERMANENT", "INVALID_RESPONSE"),
        (422, "PERMANENT", "INVALID_RESPONSE"),
        (501, "PERMANENT", "INVALID_RESPONSE"),
    ],
)
def test_default_http_classification(status, outcome, failure):
    result = default_classify(SourceResponse(status))
    assert result.outcome == ResponseOutcome(outcome)
    assert result.failure == (FailureType(failure) if failure else None)


@pytest.mark.parametrize(("kind", "failure"), [("timeout", "TIMEOUT"), ("connection", "CONNECTION")])
def test_default_transport_classification(kind, failure):
    result = default_classify(TransportError(kind))
    assert result.outcome == ResponseOutcome.TRANSIENT and result.failure == FailureType(failure)
