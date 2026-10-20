"""가짜 제공자와 Workers AI REST 제공자(응답 사례 재생)에 제공자 계약 묶음을 돌린다(FR-006, FR-007, SC-007)."""

from __future__ import annotations

import json
from collections.abc import Mapping
from pathlib import Path

import pytest

from qello_knowledge.adapters.workers_ai.rest import HttpResult, WorkersAiRestProvider
from qello_knowledge.config.loader import SecretValue
from qello_knowledge.domain.embedding import ProviderFailureKind
from qello_knowledge.embedding.fake import FakeEmbeddingProvider, fake_vector
from qello_knowledge.ports.embedder import ProviderFailure

from .embedding_provider_contract import CHECKS, MODEL, TEXTS, ProviderCase

CASES = json.loads(Path("tests/fixtures/workers_ai/cases.json").read_text(encoding="utf-8"))["cases"]
TOKEN = "t" * 40  # 시험용 가짜 토큰
ACCOUNT = "a" * 32


def _expand(value: object) -> object:
    if isinstance(value, str) and value.startswith("{{VECTORS:"):
        count, dimension = (int(part) for part in value.strip("{}").split(":")[1:])
        return [list(fake_vector(f"case-{i}", dimension)) for i in range(count)]
    if isinstance(value, dict):
        return {key: _expand(item) for key, item in value.items()}
    return value


class ReplayEmbedTransport:
    """저장된 응답 사례 하나를 돌려준다. 받은 요청을 기록한다."""

    def __init__(self, case: str) -> None:
        self.case = case
        self.requests: list[tuple[str, Mapping[str, str], bytes]] = []

    def post(self, url: str, headers: Mapping[str, str], body: bytes) -> HttpResult:
        self.requests.append((url, headers, body))
        data = CASES[self.case]
        return HttpResult(data["status"], data["headers"], json.dumps(_expand(data["body"])).encode("utf-8"))


REST_CASE_NAMES = {
    "ok": "ok_two",
    "too_long": "too_long",
    "quota": "quota",
    "transient": "rate_limited",
    "unauthorized": "unauthorized",
}


def _rest(name: str) -> WorkersAiRestProvider:
    return WorkersAiRestProvider(ACCOUNT, SecretValue(TOKEN), ReplayEmbedTransport(REST_CASE_NAMES[name]))


def _fake(name: str) -> FakeEmbeddingProvider:
    failures = {
        "too_long": ProviderFailure(ProviderFailureKind.INPUT_TOO_LONG),
        "quota": ProviderFailure(ProviderFailureKind.PROVIDER_QUOTA),
        "transient": ProviderFailure(ProviderFailureKind.TRANSIENT, 2),
        "unauthorized": ProviderFailure(ProviderFailureKind.AUTH_CONFIG),
    }
    return FakeEmbeddingProvider(fail_calls={1: failures[name]} if name in failures else None)


PROVIDERS = {
    "fake": ProviderCase(_fake),
    "workers_ai_rest": ProviderCase(_rest, secrets=(TOKEN, ACCOUNT)),
}


@pytest.mark.parametrize("check", CHECKS, ids=lambda c: c.__name__)
@pytest.mark.parametrize("provider", sorted(PROVIDERS))
def test_provider_contract(provider: str, check) -> None:
    check(PROVIDERS[provider])


def test_rest_request_shape_has_no_truncation_option() -> None:
    transport = ReplayEmbedTransport("ok_two")
    WorkersAiRestProvider(ACCOUNT, SecretValue(TOKEN), transport).embed_texts(MODEL, TEXTS)
    [(url, headers, body)] = transport.requests
    assert url == f"https://api.cloudflare.com/client/v4/accounts/{ACCOUNT}/ai/run/@cf/baai/bge-m3"
    assert headers["Authorization"] == f"Bearer {TOKEN}"
    assert json.loads(body) == {"text": list(TEXTS)}


@pytest.mark.parametrize(
    ("case", "neurons", "kind", "retry_after"),
    [
        ("ok_two", 0.01, None, None),
        ("ok_no_header", None, None, None),
        ("server_error", None, ProviderFailureKind.TRANSIENT, None),
        ("rate_limited", None, ProviderFailureKind.TRANSIENT, 2.0),
    ],
)
def test_rest_classification(case, neurons, kind, retry_after) -> None:
    provider = WorkersAiRestProvider(ACCOUNT, SecretValue(TOKEN), ReplayEmbedTransport(case))
    if kind is None:
        assert provider.embed_texts(MODEL, TEXTS).neurons == neurons
        return
    with pytest.raises(ProviderFailure) as excinfo:
        provider.embed_texts(MODEL, TEXTS)
    assert (excinfo.value.kind, excinfo.value.retry_after_seconds) == (kind, retry_after)


def test_wrong_dimension_reaches_service_check() -> None:
    provider = WorkersAiRestProvider(ACCOUNT, SecretValue(TOKEN), ReplayEmbedTransport("ok_wrong_dimension"))
    batch = provider.embed_texts(MODEL, TEXTS)
    assert {len(v) for v in batch.vectors} == {1023}  # 차원 검사는 서비스가 한다(bad_response)


def test_provider_repr_hides_token_and_account() -> None:
    text = repr(WorkersAiRestProvider(ACCOUNT, SecretValue(TOKEN)))
    assert TOKEN not in text and ACCOUNT not in text
