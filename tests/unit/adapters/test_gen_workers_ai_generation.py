"""Workers AI 생성 어댑터(QK-GEN-001 tasks T035, research R-01·R-06). 합성 응답만 쓰고 외부 호출이 없다."""

from __future__ import annotations

import json
import urllib.error

import pytest

from qello_knowledge.adapters.workers_ai import generation as gen_adapter
from qello_knowledge.adapters.workers_ai import rest
from qello_knowledge.adapters.workers_ai.generation import (
    GenerationHttpResult,
    TransportError,
    TransportTimeout,
    UrllibGenerationTransport,
    WorkersAiGenerationProvider,
    classify,
)
from qello_knowledge.config.loader import SecretValue
from qello_knowledge.domain.embedding import ProviderFailureKind
from qello_knowledge.domain.generation import GenerationFailure
from qello_knowledge.ports.embedder import ProviderFailure
from qello_knowledge.ports.generator import GenerationProviderFailure

TOKEN = "synthetic-token-value"  # 합성 값
ACCOUNT = "0" * 32


class FakeTransport:
    def __init__(self, result=None, error=None) -> None:
        self.result = result
        self.error = error
        self.sent: list[tuple[str, dict, bytes, float]] = []

    def post(self, url, headers, body, timeout):
        self.sent.append((url, dict(headers), body, timeout))
        if self.error is not None:
            raise self.error
        return self.result


def _ok(result: dict, neurons: str | None = "6.17") -> GenerationHttpResult:
    headers = {"cf-ai-neurons": neurons} if neurons is not None else {}
    return GenerationHttpResult(200, headers, json.dumps({"result": result, "success": True}).encode())


def _err(status: int, code: int | None = None, headers=None) -> GenerationHttpResult:
    body = json.dumps({"errors": [{"code": code, "message": "x"}]} if code else {"errors": []}).encode()
    return GenerationHttpResult(status, headers or {}, body)


def _provider(transport) -> WorkersAiGenerationProvider:
    return WorkersAiGenerationProvider(ACCOUNT, SecretValue(TOKEN), transport)


def test_request_body_url_and_timeout():
    transport = FakeTransport(_ok({"response": "답 [S1].", "usage": {"prompt_tokens": 10, "completion_tokens": 3}}))
    reply = _provider(transport).complete("@cf/qwen/qwen3-30b-a3b-fp8", "시스템", "사용자 /no_think", 800, 0.2, 17)
    url, headers, body, timeout = transport.sent[0]
    assert url == f"{rest.API_BASE}/accounts/{ACCOUNT}/ai/run/@cf/qwen/qwen3-30b-a3b-fp8"
    assert headers["Authorization"] == f"Bearer {TOKEN}" and timeout == 17
    assert json.loads(body) == {
        "messages": [{"role": "system", "content": "시스템"}, {"role": "user", "content": "사용자 /no_think"}],
        "max_tokens": 800,
        "temperature": 0.2,
    }
    assert (reply.text, reply.input_tokens, reply.output_tokens, reply.neurons) == ("답 [S1].", 10, 3, 6.17)
    assert reply.shape.parsed_as == "response" and reply.shape.has_usage and reply.shape.has_neurons_header
    assert TOKEN not in repr(_provider(transport))


def test_openai_shape_with_finish_reason():
    result = {
        "choices": [{"message": {"role": "assistant", "content": "답"}, "finish_reason": "length"}],
        "usage": {"prompt_tokens": 5, "completion_tokens": 800},
    }
    reply = classify(_ok(result, neurons=None))
    assert (reply.text, reply.finish_reason, reply.neurons) == ("답", "length", None)
    assert reply.shape.parsed_as == "choices" and reply.shape.has_finish_reason
    assert reply.shape.result_keys == ("choices", "usage") and reply.shape.top_keys == ("result", "success")


@pytest.mark.parametrize(
    ("result", "expected"),
    [
        # (응답, (결과 종류, 과금, 측정 Neurons)) — research R-06 표
        (_ok({"unexpected": 1}), (GenerationFailure.BAD_RESPONSE, True, 6.17)),
        (GenerationHttpResult(200, {}, b"not json"), (GenerationFailure.BAD_RESPONSE, True, None)),
        (_err(429, rest.QUOTA_CODE), (GenerationFailure.PROVIDER_QUOTA, False, None)),
        (_err(429), (GenerationFailure.TRANSIENT, True, None)),
        (_err(500), (GenerationFailure.TRANSIENT, True, None)),
        (_err(503), (GenerationFailure.TRANSIENT, True, None)),
        (_err(401), (GenerationFailure.AUTH_CONFIG, False, None)),
        (_err(403), (GenerationFailure.AUTH_CONFIG, False, None)),
        (_err(400, rest.INPUT_TOO_LONG_CODE), (GenerationFailure.INPUT_TOO_LONG, False, None)),
        (_err(400), (GenerationFailure.BAD_RESPONSE, False, None)),
        (_err(404), (GenerationFailure.BAD_RESPONSE, False, None)),
        (_err(413), (GenerationFailure.BAD_RESPONSE, False, None)),
        (_err(422), (GenerationFailure.BAD_RESPONSE, False, None)),
    ],
)
def test_billability_table(result, expected):
    with pytest.raises(GenerationProviderFailure) as caught:
        classify(result)
    failure = caught.value
    assert (failure.kind, failure.billable, failure.neurons) == expected
    assert str(failure) == failure.kind.value  # 문구에 본문·토큰이 없다


def test_bad_response_keeps_shape_names_only():
    with pytest.raises(GenerationProviderFailure) as caught:
        classify(_ok({"output": "비밀 같은 본문"}))
    assert caught.value.shape.result_keys == ("output",)
    assert "비밀 같은 본문" not in repr(caught.value.shape)


def test_retry_after_is_passed():
    with pytest.raises(GenerationProviderFailure) as caught:
        classify(_err(429, headers={"Retry-After": "1.5"}))
    assert caught.value.retry_after_seconds == 1.5


@pytest.mark.parametrize(
    ("error", "kind"),
    [(TransportTimeout(), GenerationFailure.TIMEOUT), (TransportError("x"), GenerationFailure.TRANSIENT)],
)
def test_transport_errors_map_to_kinds(error, kind):
    with pytest.raises(GenerationProviderFailure) as caught:
        _provider(FakeTransport(error=error)).complete("@cf/qwen/qwen3-8b", "s", "u", 10, 0.2, 5)
    assert caught.value.kind is kind and caught.value.billable


_SAME_RULE = {
    ProviderFailureKind.TRANSIENT: GenerationFailure.TRANSIENT,
    ProviderFailureKind.PROVIDER_QUOTA: GenerationFailure.PROVIDER_QUOTA,
    ProviderFailureKind.AUTH_CONFIG: GenerationFailure.AUTH_CONFIG,
    ProviderFailureKind.INPUT_TOO_LONG: GenerationFailure.INPUT_TOO_LONG,
    ProviderFailureKind.BAD_RESPONSE: GenerationFailure.BAD_RESPONSE,
}


@pytest.mark.parametrize(
    ("status", "code"),
    [(429, rest.QUOTA_CODE), (429, None), (500, None), (502, None), (401, None), (403, None),
     (400, rest.INPUT_TOO_LONG_CODE), (400, None), (404, None)],
)  # fmt: skip
def test_error_classification_matches_embedding_rule(status, code):
    """`rest.py` 오류 판정과 같은 상태·오류 코드에 같은 종류를 낸다(research R-01)."""
    response = _err(status, code)
    with pytest.raises(ProviderFailure) as embedding:
        rest.classify(rest.HttpResult(response.status, response.headers, response.body))
    with pytest.raises(GenerationProviderFailure) as generation:
        classify(response)
    assert _SAME_RULE[embedding.value.kind] is generation.value.kind


class _Opener:
    def __init__(self, error) -> None:
        self.error = error

    def __call__(self, request, timeout):
        raise self.error


@pytest.mark.parametrize(
    ("error", "raised"),
    [
        (TimeoutError(), TransportTimeout),
        (TimeoutError(), TransportTimeout),
        (urllib.error.URLError(TimeoutError()), TransportTimeout),
        (urllib.error.URLError(ConnectionRefusedError()), TransportError),
        (ConnectionResetError(), TransportError),
    ],
)
def test_urllib_transport_separates_timeout(monkeypatch, error, raised):
    monkeypatch.setattr(gen_adapter.urllib.request, "urlopen", _Opener(error))
    with pytest.raises(raised):
        UrllibGenerationTransport().post("https://api.cloudflare.com/x", {}, b"{}", 3)
