"""Workers AI REST 생성 제공자(QK-GEN-001 research R-01·R-06).

`POST /client/v4/accounts/{account}/ai/run/{model}`에 `{"messages": [...], "max_tokens", "temperature"}`를 보낸다.
응답 꼴은 두 가지를 받는다. (a) `result.response` + `result.usage`,
(b) `result.choices[0].message.content` + `finish_reason` + `result.usage`.
`rest.py`는 바꾸지 않고 공개 상수만 가져온다. 오류 판정은 `rest.py`와 같은 규칙을 여기 따로 두고 표 시험으로 고정한다.
토큰은 이 파일 안에서만 꺼내고, 예외 문구에 토큰·계정 ID·본문을 넣지 않는다.
"""

from __future__ import annotations

import http.client
import json
import socket
import urllib.error
import urllib.request
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any, Protocol
from urllib.parse import quote

from qello_knowledge.adapters.workers_ai.rest import API_BASE, INPUT_TOO_LONG_CODE, NEURONS_HEADER, QUOTA_CODE
from qello_knowledge.config.loader import SecretValue
from qello_knowledge.domain.generation import GenerationFailure, ProviderReply, ResponseShape
from qello_knowledge.ports.generator import GenerationProviderFailure


@dataclass(frozen=True)
class GenerationHttpResult:
    status: int
    headers: Mapping[str, str]
    body: bytes


class TransportTimeout(Exception):  # noqa: N818 - 전송 계층 신호 이름
    """호출 시간 제한에 걸렸다."""


class TransportError(Exception):
    """연결·읽기 실패. 일시 실패로 본다."""


class GenerationTransport(Protocol):
    def post(self, url: str, headers: Mapping[str, str], body: bytes, timeout: float) -> GenerationHttpResult: ...


class UrllibGenerationTransport:
    """표준 라이브러리 전송. 시간 제한을 호출마다 받고, 시간 초과를 따로 알린다(spec FR-002)."""

    def post(self, url: str, headers: Mapping[str, str], body: bytes, timeout: float) -> GenerationHttpResult:
        request = urllib.request.Request(url, data=body, headers=dict(headers), method="POST")  # noqa: S310 - 고정 https 주소
        try:
            try:
                with urllib.request.urlopen(request, timeout=timeout) as response:  # noqa: S310 - 고정 https 주소
                    return GenerationHttpResult(response.status, dict(response.headers.items()), response.read())
            except urllib.error.HTTPError as error:
                return GenerationHttpResult(error.code, dict(error.headers.items()), error.read())
        except TimeoutError:
            raise TransportTimeout from None
        except urllib.error.URLError as error:
            if isinstance(error.reason, (TimeoutError, socket.timeout)):
                raise TransportTimeout from None
            raise TransportError(type(error).__name__) from None
        except (http.client.HTTPException, OSError) as error:
            raise TransportError(type(error).__name__) from None


def _header(headers: Mapping[str, str], name: str) -> str | None:
    for key, value in headers.items():
        if key.lower() == name:
            return value
    return None


def _neurons(headers: Mapping[str, str]) -> float | None:
    value = _header(headers, NEURONS_HEADER)
    try:
        neurons = float(value) if value is not None else None
    except ValueError:
        return None
    return neurons if neurons is not None and neurons >= 0 else None


def _retry_after(headers: Mapping[str, str]) -> float | None:
    value = _header(headers, "retry-after")
    try:
        seconds = float(value) if value is not None else None
    except ValueError:
        return None
    return seconds if seconds is not None and seconds >= 0 else None


def _error_codes(body: bytes) -> set[int]:
    try:
        data = json.loads(body)
    except (ValueError, UnicodeDecodeError):
        return set()
    errors = data.get("errors") if isinstance(data, dict) else None
    if not isinstance(errors, list):
        return set()
    return {e["code"] for e in errors if isinstance(e, dict) and isinstance(e.get("code"), int)}


def _int_or_none(value: Any) -> int | None:
    return value if isinstance(value, int) and not isinstance(value, bool) and value >= 0 else None


def _usage(result: Mapping[str, Any]) -> tuple[int | None, int | None]:
    usage = result.get("usage")
    if not isinstance(usage, dict):
        return None, None
    prompt = usage.get("prompt_tokens", usage.get("input_tokens"))
    completion = usage.get("completion_tokens", usage.get("output_tokens"))
    return _int_or_none(prompt), _int_or_none(completion)


def parse_success(result: GenerationHttpResult) -> ProviderReply:
    """2xx 응답을 해석한다. 두 꼴이 모두 아니면 `bad_response`(과금됨)."""
    neurons = _neurons(result.headers)
    try:
        data = json.loads(result.body)
    except (ValueError, UnicodeDecodeError):
        data = None
    top = data if isinstance(data, dict) else {}
    body = top.get("result") if isinstance(top.get("result"), dict) else {}
    input_tokens, output_tokens = _usage(body)
    text: str | None = None
    finish: str | None = None
    parsed_as: str | None = None
    if isinstance(body.get("response"), str):
        text, parsed_as = body["response"], "response"
    else:
        choices = body.get("choices")
        first = choices[0] if isinstance(choices, list) and choices and isinstance(choices[0], dict) else None
        message = first.get("message") if first else None
        if isinstance(message, dict) and isinstance(message.get("content"), str):
            text, parsed_as = message["content"], "choices"
            finish = first.get("finish_reason") if isinstance(first.get("finish_reason"), str) else None
    shape = ResponseShape(
        top_keys=tuple(sorted(top)),
        result_keys=tuple(sorted(body)),
        has_usage=isinstance(body.get("usage"), dict),
        has_neurons_header=neurons is not None,
        has_finish_reason=finish is not None,
        parsed_as=parsed_as,
    )
    if text is None:
        raise GenerationProviderFailure(
            GenerationFailure.BAD_RESPONSE,
            billable=True,
            neurons=neurons,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            shape=shape,
        )
    return ProviderReply(text, input_tokens, output_tokens, neurons, finish, shape)


def classify(result: GenerationHttpResult) -> ProviderReply:
    """research R-06 표. 2xx가 아니면 `GenerationProviderFailure`."""
    status = result.status
    if 200 <= status < 300:
        return parse_success(result)
    codes = _error_codes(result.body)
    if status == 400 and INPUT_TOO_LONG_CODE in codes:
        raise GenerationProviderFailure(GenerationFailure.INPUT_TOO_LONG, billable=False)
    if status == 429 and QUOTA_CODE in codes:
        raise GenerationProviderFailure(GenerationFailure.PROVIDER_QUOTA, billable=False)
    if status == 429 or status >= 500:
        raise GenerationProviderFailure(
            GenerationFailure.TRANSIENT, billable=True, retry_after_seconds=_retry_after(result.headers)
        )
    if status in {401, 403}:
        raise GenerationProviderFailure(GenerationFailure.AUTH_CONFIG, billable=False)
    raise GenerationProviderFailure(GenerationFailure.BAD_RESPONSE, billable=False)


class WorkersAiGenerationProvider:
    """`GenerationProvider` 구현. 재시도는 하지 않는다."""

    def __init__(self, account_id: str, api_token: SecretValue, transport: GenerationTransport | None = None) -> None:
        self._account_id = account_id
        self._token = api_token
        self._transport = transport or UrllibGenerationTransport()

    def __repr__(self) -> str:
        return "WorkersAiGenerationProvider()"

    def _url(self, model_id: str) -> str:
        return f"{API_BASE}/accounts/{quote(self._account_id, safe='')}/ai/run/{model_id}"

    def complete(
        self, model_id: str, system: str, user: str, max_tokens: int, temperature: float, timeout_seconds: float
    ) -> ProviderReply:
        headers = {"Authorization": f"Bearer {self._token.reveal()}", "Content-Type": "application/json"}
        payload = {
            "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
            "max_tokens": max_tokens,
            "temperature": temperature,
        }
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        try:
            result = self._transport.post(self._url(model_id), headers, body, timeout_seconds)
        except TransportTimeout:
            raise GenerationProviderFailure(GenerationFailure.TIMEOUT, billable=True) from None
        except TransportError:
            raise GenerationProviderFailure(GenerationFailure.TRANSIENT, billable=True) from None
        return classify(result)
