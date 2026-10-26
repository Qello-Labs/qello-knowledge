"""Discord 상호작용 웹후크. 전송 실패 값에는 원문·경로·자격 정보를 넣지 않는다."""

from __future__ import annotations

import json
import math
import ssl
import threading
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from http.client import HTTPException
from importlib.metadata import PackageNotFoundError, version
from time import monotonic, sleep
from typing import Protocol
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import HTTPRedirectHandler, HTTPSHandler, Request, build_opener

from qello_knowledge.domain.discord import QueryStage, RenderedReply

API_ORIGIN = "https://discord.com"
try:
    PACKAGE_VERSION = version("qello-knowledge")
except PackageNotFoundError:
    PACKAGE_VERSION = "0.1.0"
USER_AGENT = f"DiscordBot (https://github.com/Qello-Labs/qello-knowledge, {PACKAGE_VERSION})"


@dataclass(frozen=True)
class DiscordResponse:
    status: int
    body: Mapping[str, object] = field(default_factory=dict, repr=False)


class Transport(Protocol):
    def request(
        self, method: str, path: str, headers: Mapping[str, str], body: object, *, timeout: float, deadline: float
    ) -> DiscordResponse: ...


class _NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


class _DiscordRequest(Request):
    def __init__(self, path: str, *, headers: Mapping[str, str], body: object, method: str):
        if not path.startswith("/api/v10/") or any(c in path for c in "\r\n"):
            raise ValueError("invalid Discord API path")
        super().__init__(
            API_ORIGIN + path,
            data=json.dumps(body, ensure_ascii=False).encode(),
            headers={**headers, "Content-Type": "application/json"},
            method=method,
        )


class UrllibTransport:
    """소켓 제한에 더해 헤더·본문 수신 전체에 절대 마감을 적용한다.

    urllib 호출은 중단할 수 없으므로 대기 스레드를 분리한다. 마감 뒤 결과는 버리고,
    호출이 실제로 돌아오는 즉시 응답을 닫는다. 이 스레드는 재시도나 로그를 하지 않는다.
    """

    def __init__(self, *, opener=None, clock: Callable[[], float] = monotonic):
        self._clock = clock
        self._opener = (
            opener
            if opener is not None
            else build_opener(
                _NoRedirect(),
                HTTPSHandler(context=ssl.create_default_context()),
            )
        )

    def request(
        self, method: str, path: str, headers: Mapping[str, str], body: object, *, timeout: float, deadline: float
    ) -> DiscordResponse:
        outgoing = _DiscordRequest(path, headers=headers, body=body, method=method)
        limit = min(timeout, deadline - self._clock())
        if limit <= 0:
            raise TimeoutError("timeout")
        done = threading.Event()
        result: list[DiscordResponse] = []
        failure: list[str] = []

        def send() -> None:
            response = None
            try:
                try:
                    response = self._opener.open(outgoing, timeout=limit)
                except HTTPError as error:
                    response = error
                raw = response.read(65537)
                try:
                    payload = json.loads(raw) if len(raw) <= 65536 else {}
                except (ValueError, UnicodeError, RecursionError):
                    payload = {}
                result.append(DiscordResponse(response.status, payload if isinstance(payload, dict) else {}))
            except TimeoutError:
                failure.append("timeout")
            except URLError as error:
                failure.append("timeout" if isinstance(error.reason, TimeoutError) else "connection")
            except Exception:
                # 전송 스레드 경계: 예상 밖 오류도 자격 정보가 든 traceback으로 나가지 않는다.
                failure.append("connection")
            finally:
                if response is not None:
                    try:
                        response.close()
                    except Exception:
                        failure.append("connection")
                done.set()

        threading.Thread(target=send, daemon=True, name="discord-http").start()
        if not done.wait(max(0, min(limit, deadline - self._clock()))):
            raise TimeoutError("timeout")
        if self._clock() > deadline:
            raise TimeoutError("timeout")
        if failure:
            if failure[0] == "timeout":
                raise TimeoutError("timeout") from None
            raise OSError("connection") from None
        if not result:
            raise OSError("connection")
        return result[0]


@dataclass(frozen=True)
class DeliveryResult:
    stage: QueryStage
    failure: str | None
    retries: int
    calls: int


@dataclass(frozen=True)
class RegistrationResult:
    status: int | None
    failure: str | None


class DiscordWebhook:
    def __init__(
        self,
        application_id: str,
        *,
        transport: Transport | None = None,
        clock: Callable[[], float] = monotonic,
        sleep: Callable[[float], None] = sleep,
    ):
        self._application_id = application_id
        self._clock = clock
        self._sleep = sleep
        self._transport = transport if transport is not None else UrllibTransport(clock=clock)

    def _request(
        self, method: str, path: str, body: object, deadline: float, token: str | None = None
    ) -> DiscordResponse:
        headers = {"User-Agent": USER_AGENT}
        if token is not None:
            headers["Authorization"] = "Bot " + token
        return self._transport.request(
            method, path, headers, body, timeout=min(3, deadline - self._clock()), deadline=deadline
        )

    def deliver(self, token: str, reply: RenderedReply, *, deadline: float) -> DeliveryResult:
        calls = retries = 0
        base = f"/api/v10/webhooks/{quote(self._application_id, safe='')}/{quote(token, safe='')}"
        for index, content in enumerate(reply.messages):
            path = base + "/messages/@original" if index == 0 else base
            method = "PATCH" if index == 0 else "POST"
            body: dict[str, object] = {"content": content, "allowed_mentions": {"parse": []}}
            if index and reply.ephemeral:
                body["flags"] = 64
            for attempt in range(2):
                if deadline - self._clock() < 1:
                    return DeliveryResult(QueryStage.UNDELIVERED, "deadline", retries, calls)
                calls += 1
                if attempt:
                    retries += 1
                wait: float | None = None
                try:
                    response = self._request(method, path, body, deadline)
                    if self._clock() > deadline:
                        return DeliveryResult(QueryStage.UNDELIVERED, "deadline", retries, calls)
                    if 200 <= response.status < 300:
                        break
                    failure = "http_" + str(response.status)
                    if response.status == 429:
                        raw_wait = response.body.get("retry_after")
                        if type(raw_wait) in (int, float) and math.isfinite(raw_wait) and raw_wait >= 0:
                            wait = float(raw_wait)
                    elif 500 <= response.status < 600 or (response.status == 404 and index == 0):
                        wait = 1
                except TimeoutError:
                    failure, wait = "timeout", 1
                except (OSError, HTTPException):
                    failure, wait = "connection", 1
                if attempt or wait is None or wait + 1 > deadline - self._clock():
                    return DeliveryResult(QueryStage.UNDELIVERED, failure, retries, calls)
                self._sleep(wait)
        return DeliveryResult(QueryStage.DONE, None, retries, calls)

    def register_commands(
        self, guild_id: str, token: str, commands: list[dict[str, object]], *, deadline: float
    ) -> RegistrationResult:
        if deadline - self._clock() < 1:
            return RegistrationResult(None, "deadline")
        path = (
            f"/api/v10/applications/{quote(self._application_id, safe='')}/guilds/{quote(guild_id, safe='')}/commands"
        )
        try:
            response = self._request("PUT", path, commands, deadline, token)
            if self._clock() > deadline:
                return RegistrationResult(None, "deadline")
            return RegistrationResult(response.status, None if 200 <= response.status < 300 else "http")
        except TimeoutError:
            return RegistrationResult(None, "timeout")
        except (OSError, HTTPException):
            return RegistrationResult(None, "connection")
