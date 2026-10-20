"""Workers AI REST 임베딩 제공자(research R-09). 색인 경로에서 쓴다.

`POST /client/v4/accounts/{account}/ai/run/{model}`에 `{"text": [...]}`를 보낸다.
입력을 자르는 옵션은 보내지 않는다(FR-003).
토큰은 이 파일 안에서만 꺼내고, 예외 문구에 토큰·계정 ID·텍스트를 넣지 않는다(FR-007).
"""

from __future__ import annotations

import json
import urllib.error
import urllib.request
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Protocol
from urllib.parse import quote

from qello_knowledge.config.loader import SecretValue
from qello_knowledge.domain.embedding import ModelSpec, ProviderFailureKind
from qello_knowledge.ports.embedder import ProviderBatch, ProviderFailure

API_BASE = "https://api.cloudflare.com/client/v4"
INPUT_TOO_LONG_CODE = 3030
QUOTA_CODE = 3036
NEURONS_HEADER = "cf-ai-neurons"
TIMEOUT_SECONDS = 60


@dataclass(frozen=True)
class HttpResult:
    status: int
    headers: Mapping[str, str]
    body: bytes


class NetworkError(Exception):
    """연결 실패·시간 초과. 일시 오류로 본다."""


class EmbedTransport(Protocol):
    def post(self, url: str, headers: Mapping[str, str], body: bytes) -> HttpResult: ...


class UrllibTransport:
    """표준 라이브러리 전송(런타임 의존성 0, research R-09)."""

    def __init__(self, timeout: float = TIMEOUT_SECONDS) -> None:
        self._timeout = timeout

    def post(self, url: str, headers: Mapping[str, str], body: bytes) -> HttpResult:
        request = urllib.request.Request(url, data=body, headers=dict(headers), method="POST")  # noqa: S310 - 고정 https 주소
        try:
            with urllib.request.urlopen(request, timeout=self._timeout) as response:  # noqa: S310 - 고정 https 주소
                return HttpResult(response.status, dict(response.headers.items()), response.read())
        except urllib.error.HTTPError as error:
            return HttpResult(error.code, dict(error.headers.items()), error.read())
        except (urllib.error.URLError, TimeoutError, OSError) as error:
            raise NetworkError(type(error).__name__) from None


def _error_codes(body: bytes) -> set[int]:
    try:
        data = json.loads(body)
    except (ValueError, UnicodeDecodeError):
        return set()
    errors = data.get("errors") if isinstance(data, dict) else None
    if not isinstance(errors, list):
        return set()
    return {e["code"] for e in errors if isinstance(e, dict) and isinstance(e.get("code"), int)}


def _retry_after(headers: Mapping[str, str]) -> float | None:
    value = _header(headers, "retry-after")
    if value is None:
        return None
    try:
        seconds = float(value)
    except ValueError:
        return None
    return seconds if seconds >= 0 else None


def _header(headers: Mapping[str, str], name: str) -> str | None:
    for key, value in headers.items():
        if key.lower() == name:
            return value
    return None


def _neurons(headers: Mapping[str, str]) -> float | None:
    value = _header(headers, NEURONS_HEADER)
    if value is None:
        return None
    try:
        neurons = float(value)
    except ValueError:
        return None
    return neurons if neurons >= 0 else None


def _vectors(body: bytes) -> tuple[tuple[float, ...], ...]:
    try:
        data = json.loads(body)
        rows = data["result"]["data"]
        return tuple(tuple(float(v) for v in row) for row in rows)
    except (ValueError, KeyError, TypeError, UnicodeDecodeError):
        raise ProviderFailure(ProviderFailureKind.BAD_RESPONSE) from None


def classify(result: HttpResult) -> ProviderBatch:
    """research R-09 표대로 응답을 결과나 `ProviderFailure`로 바꾼다. 개수·차원 검사는 서비스가 한다."""
    status = result.status
    if 200 <= status < 300:
        return ProviderBatch(_vectors(result.body), _neurons(result.headers))
    codes = _error_codes(result.body)
    if status == 400 and INPUT_TOO_LONG_CODE in codes:
        raise ProviderFailure(ProviderFailureKind.INPUT_TOO_LONG)
    if status == 429 and QUOTA_CODE in codes:
        raise ProviderFailure(ProviderFailureKind.PROVIDER_QUOTA)
    if status == 429 or status >= 500:
        raise ProviderFailure(ProviderFailureKind.TRANSIENT, _retry_after(result.headers))
    if status in {401, 403}:
        raise ProviderFailure(ProviderFailureKind.AUTH_CONFIG)
    raise ProviderFailure(ProviderFailureKind.BAD_RESPONSE)


class WorkersAiRestProvider:
    """`EmbeddingProvider` 구현. 재시도는 하지 않는다."""

    def __init__(self, account_id: str, api_token: SecretValue, transport: EmbedTransport | None = None) -> None:
        self._account_id = account_id
        self._token = api_token
        self._transport = transport or UrllibTransport()

    def __repr__(self) -> str:
        return "WorkersAiRestProvider()"

    def _url(self, model: ModelSpec) -> str:
        return f"{API_BASE}/accounts/{quote(self._account_id, safe='')}/ai/run/{model.model_version}"

    def embed_texts(self, model: ModelSpec, texts: Sequence[str]) -> ProviderBatch:
        headers = {"Authorization": f"Bearer {self._token.reveal()}", "Content-Type": "application/json"}
        body = json.dumps({"text": list(texts)}, ensure_ascii=False).encode("utf-8")
        try:
            result = self._transport.post(self._url(model), headers, body)
        except NetworkError:
            raise ProviderFailure(ProviderFailureKind.TRANSIENT) from None
        return classify(result)
