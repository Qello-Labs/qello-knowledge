import io
import ssl
from urllib.error import HTTPError, URLError
from urllib.request import HTTPRedirectHandler

import pytest

from qello_knowledge.adapters.http import HttpsTransport
from qello_knowledge.config.loader import SecretValue
from qello_knowledge.domain.source import SourceRequest, TransportError

TOKEN = "gh" + "p_" + "A" * 36


class Response(io.BytesIO):
    status = 200
    headers = {"X-RateLimit-Remaining": "10"}


class Opener:
    def __init__(self, response=None, error=None):
        self.response = response
        self.error = error
        self.requests = []

    def open(self, request, timeout):
        self.requests.append((request, timeout))
        if self.error is not None:
            raise self.error
        return self.response


@pytest.mark.parametrize("size,limit,truncated", [(5, 4, True), (4, 4, False), (3, 4, False)])
def test_response_bounds_headers_and_status(size, limit, truncated, caplog):
    opener = Opener(Response(b"x" * size))
    transport = HttpsTransport(("api.github.com",), SecretValue(TOKEN), opener=opener)
    result = transport.send(SourceRequest("GET", "https://api.github.com/repos/x/y", max_bytes=limit))
    assert result.status == 200 and result.headers == {"x-ratelimit-remaining": "10"}
    assert result.body == b"x" * min(size, limit) and result.truncated == truncated
    assert not caplog.records


@pytest.mark.parametrize("status", [302, 404, 500])
def test_http_errors_are_responses(status):
    error = HTTPError(
        "https://api.github.com/x", status, TOKEN, {"Location": "https://other.invalid/x"}, io.BytesIO(b"x")
    )
    result = HttpsTransport((), None, opener=Opener(error=error)).send(SourceRequest("GET", error.url))
    assert result.status == status and result.body == b"x"
    assert result.headers["location"] == "https://other.invalid/x"


@pytest.mark.parametrize(
    "error,kind",
    [
        (TimeoutError(TOKEN), "timeout"),
        (URLError(TOKEN), "connection"),
        (ConnectionError(TOKEN), "connection"),
        (ssl.SSLError(TOKEN), "connection"),
    ],
)
def test_errors_are_safe(error, kind, caplog):
    # Python 3.13의 socket.timeout은 TimeoutError의 별칭이다.
    transport = HttpsTransport(("api.github.com",), SecretValue(TOKEN), opener=Opener(error=error))
    with pytest.raises(TransportError) as raised:
        transport.send(SourceRequest("GET", "https://api.github.com/x"))
    assert str(raised.value) == kind
    assert raised.value.__suppress_context__
    assert TOKEN not in repr(transport) + str(transport) + repr(raised.value)
    assert not caplog.records


@pytest.mark.parametrize("host,authorized", [("api.github.com", True), ("other.invalid", False)])
def test_headers_auth_host_and_override(host, authorized):
    opener = Opener(Response(b""))
    transport = HttpsTransport(("api.github.com",), SecretValue(TOKEN), opener=opener)
    transport.send(
        SourceRequest(
            "GET",
            f"https://{host}/x",
            {"user-agent": "test", "x-github-api-version": "new", "authorization": "untrusted"},
        )
    )
    request, timeout = opener.requests[0]
    headers = {key.lower(): value for key, value in request.header_items()}
    assert headers["user-agent"] == "test" and headers["x-github-api-version"] == "new"
    assert headers.get("authorization") == ("Bearer " + TOKEN if authorized else None)
    assert timeout == 30


def test_default_opener_disables_redirects_and_verifies_tls():
    transport = HttpsTransport((), None)
    handlers = transport._opener.handlers
    redirect = next(handler for handler in handlers if isinstance(handler, HTTPRedirectHandler))
    assert redirect.redirect_request(None, None, 302, "", {}, "https://other.invalid") is None
    context = next(handler._context for handler in handlers if hasattr(handler, "_context"))
    assert context.check_hostname and context.verify_mode == ssl.CERT_REQUIRED
    opener = Opener(Response(b""))
    HttpsTransport((), None, opener=opener).send(SourceRequest("GET", "https://api.github.com/x"))
    headers = {key.lower(): value for key, value in opener.requests[0][0].header_items()}
    assert headers["user-agent"] == "qello-knowledge-indexer"
    assert headers["x-github-api-version"] == "2022-11-28"


@pytest.mark.parametrize("url", ["http://api.github.com/x", "file:///tmp/synthetic", "ftp://api.github.com/x"])
def test_only_https_requests_reach_opener(url):
    opener = Opener(Response(b""))
    transport = HttpsTransport((), None, opener=opener)
    with pytest.raises(TransportError, match="connection"):
        transport.send(SourceRequest("GET", url))
    assert opener.requests == []


@pytest.mark.parametrize("stage", ["open", "read"])
@pytest.mark.parametrize("exception_name", ["IncompleteRead", "BadStatusLine"])
def test_http_protocol_errors_become_connection_errors(stage, exception_name, caplog):
    from http.client import BadStatusLine, IncompleteRead

    error = IncompleteRead(b"x") if exception_name == "IncompleteRead" else BadStatusLine("x")

    class BrokenResponse(Response):
        def read(self, size=-1):
            raise error

    opener = Opener(error=error) if stage == "open" else Opener(BrokenResponse(b""))
    transport = HttpsTransport(("api.github.com",), SecretValue(TOKEN), opener=opener)
    with pytest.raises(TransportError, match="^connection$") as raised:
        transport.send(SourceRequest("GET", "https://api.github.com/x", max_bytes=10))
    assert raised.value.kind == "connection" and raised.value.__suppress_context__
    assert TOKEN not in repr(raised.value) and not caplog.records


@pytest.mark.parametrize("stage", ["open", "read"])
def test_url_error_with_timeout_reason_remains_timeout(stage):
    # socket.timeout과 TimeoutError는 같은 예외 타입이다.
    error = URLError(TimeoutError("synthetic timeout"))

    class BrokenResponse(Response):
        def read(self, size=-1):
            raise error

    opener = Opener(error=error) if stage == "open" else Opener(BrokenResponse(b""))
    with pytest.raises(TransportError, match="^timeout$") as raised:
        HttpsTransport((), None, opener=opener).send(SourceRequest("GET", "https://api.github.com/x"))
    assert raised.value.kind == "timeout"


def test_injected_authorization_and_default_headers_replace_github_defaults():
    opener = Opener(Response(b"{}"))
    transport = HttpsTransport(
        ("api.atlassian.com",),
        None,
        authorization=lambda: "Basic dGVzdA==",
        default_headers={"accept": "application/json"},
        opener=opener,
    )
    transport.send(SourceRequest("GET", "https://api.atlassian.com/ex/confluence/c/wiki/api/v2/spaces"))
    sent = {k.lower(): v for k, v in opener.requests[0][0].header_items()}
    assert sent["authorization"] == "Basic dGVzdA=="
    assert sent["accept"] == "application/json"
    assert "x-github-api-version" not in sent
    assert sent["user-agent"] == "qello-knowledge-indexer"


def test_injected_authorization_only_for_auth_hosts():
    opener = Opener(Response(b"{}"))
    transport = HttpsTransport(("api.atlassian.com",), None, authorization=lambda: "Basic dGVzdA==", opener=opener)
    transport.send(SourceRequest("GET", "https://other.invalid/x"))
    sent = {k.lower(): v for k, v in opener.requests[0][0].header_items()}
    assert "authorization" not in sent


def test_github_headers_are_unchanged_without_injection():
    opener = Opener(Response(b"{}"))
    HttpsTransport(("api.github.com",), SecretValue(TOKEN), opener=opener).send(
        SourceRequest("GET", "https://api.github.com/repos/x/y")
    )
    sent = {k.lower(): v for k, v in opener.requests[0][0].header_items()}
    assert sent == {
        "user-agent": "qello-knowledge-indexer",
        "x-github-api-version": "2022-11-28",
        "authorization": "Bearer " + TOKEN,
    }
