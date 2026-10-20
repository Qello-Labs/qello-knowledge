"""TLS 검증·인증 호스트 제한을 적용하는 읽기 전송. 로그를 남기지 않는다."""

import ssl
from collections.abc import Mapping
from email.message import Message
from http.client import HTTPException
from typing import IO
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import HTTPRedirectHandler, HTTPSHandler, OpenerDirector, Request, build_opener

from qello_knowledge.config.loader import SecretValue
from qello_knowledge.domain.source import SourceRequest, SourceResponse, TransportError


class _NoRedirect(HTTPRedirectHandler):
    def redirect_request(
        self, req: Request, fp: IO[bytes], code: int, msg: str, headers: Message, newurl: str
    ) -> Request | None:
        return None


class _HttpsRequest(Request):
    def __init__(self, url: str, *, headers: Mapping[str, str], method: str) -> None:
        parts = urlsplit(url)
        if parts.scheme != "https" or parts.hostname is None:
            raise ValueError("HTTPS 요청이 필요하다")
        super().__init__(url, headers=dict(headers), method=method)


class HttpsTransport:
    def __init__(
        self,
        auth_hosts: tuple[str, ...],
        token: SecretValue | None,
        *,
        user_agent: str = "qello-knowledge-indexer",
        timeout_seconds: float = 30,
        opener: OpenerDirector | None = None,
    ) -> None:
        self._auth_hosts = auth_hosts
        self._token = token
        self._user_agent = user_agent
        self._timeout = timeout_seconds
        self._opener = (
            opener
            if opener is not None
            else build_opener(_NoRedirect(), HTTPSHandler(context=ssl.create_default_context()))
        )

    def send(self, request: SourceRequest) -> SourceResponse:
        headers = {"user-agent": self._user_agent, "x-github-api-version": "2022-11-28"}
        headers.update({k.lower(): v for k, v in request.headers.items() if k.lower() != "authorization"})
        if urlsplit(request.url).hostname in self._auth_hosts and self._token is not None:
            headers["authorization"] = "Bearer " + self._token.reveal()
        try:
            outgoing = _HttpsRequest(request.url, headers=headers, method=request.method)
            try:
                response = self._opener.open(outgoing, timeout=self._timeout)
            except HTTPError as error:
                response = error
            with response:
                body = response.read() if request.max_bytes is None else response.read(request.max_bytes + 1)
                truncated = request.max_bytes is not None and len(body) > request.max_bytes
                return SourceResponse(
                    response.status,
                    dict(response.headers.items()),
                    body[: request.max_bytes] if truncated else body,
                    truncated,
                )
        except TimeoutError:
            raise TransportError("timeout") from None
        except URLError as error:
            kind = "timeout" if isinstance(error.reason, TimeoutError) else "connection"
            raise TransportError(kind) from None
        except (OSError, ValueError, HTTPException):
            raise TransportError("connection") from None
