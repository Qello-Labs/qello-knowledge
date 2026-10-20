"""US1: 순서·차원·모델 버전, 빈 입력, 출처 없는 색인 입력, 전송 직전 비밀값 검사(AS1, AS5, FR-005, SC-006)."""

import logging

import pytest

from qello_knowledge.domain.embedding import (
    EmbedError,
    EmbedErrorKind,
    EmbedFailureKind,
    EmbedInput,
    EmbedPurpose,
    EmbedRequest,
)
from qello_knowledge.embedding.fake import fake_vector
from qello_knowledge.security.exceptions import SecretException
from tests.unit.embedding.helpers import MODEL, index_request, query_request
from tests.unit.synthetic_secrets import SYNTHETIC

TOKEN = SYNTHETIC["github-classic"]


def test_vectors_keep_order_dimension_and_model_version(make_harness) -> None:
    harness = make_harness()
    result = harness.embedder.embed(index_request(["하나", "둘", "셋"]))
    assert result.model_version == MODEL and result.dimension == 1024
    assert [item.index for item in result.items] == [0, 1, 2]
    assert [item.vector for item in result.items] == [fake_vector(t, 1024) for t in ["하나", "둘", "셋"]]
    assert all(len(item.vector or ()) == 1024 and item.failure is None for item in result.items)
    assert result.summary.requested == 3 and result.summary.provider_calls == 1


def test_result_has_no_provider_types(make_harness) -> None:
    result = make_harness().embedder.embed(index_request(["하나"]))
    module_names = {type(value).__module__ for value in (result, result.items[0], result.summary)}
    assert module_names == {"qello_knowledge.domain.embedding"}


@pytest.mark.parametrize("text", ["", "   \n\t"])
def test_empty_input_fails_without_call(make_harness, text) -> None:
    harness = make_harness()
    result = harness.embedder.embed(index_request([text, "정상"]))
    assert result.items[0].failure is EmbedFailureKind.EMPTY_INPUT
    assert result.items[1].vector is not None
    assert harness.provider.sent_texts == ["정상"]


def test_index_input_without_origin_is_not_sent(make_harness) -> None:
    harness = make_harness()
    inputs = (EmbedInput("출처 없음"), EmbedInput("출처 있음", ("docs", "a.md")))
    request = EmbedRequest(inputs, EmbedPurpose.INDEX, MODEL, "r")
    result = harness.embedder.embed(request)
    assert result.items[0].failure is EmbedFailureKind.NO_ORIGIN
    assert harness.provider.sent_texts == ["출처 있음"]


def test_secret_text_is_blocked_and_rest_of_batch_is_sent(make_harness, caplog) -> None:
    caplog.set_level(logging.INFO)
    harness = make_harness()
    result = harness.embedder.embed(index_request(["앞", f"설정\n{TOKEN}", "뒤"]))
    assert [item.failure for item in result.items] == [None, EmbedFailureKind.SECRET_BLOCKED, None]
    assert harness.provider.sent_texts == ["앞", "뒤"]
    assert result.summary.failures == {"secret_blocked": 1}
    assert "embed_secret_blocked item=1 rule=github-token line=2" in caplog.text
    assert TOKEN not in caplog.text and "설정" not in caplog.text


def test_exception_for_that_origin_lets_text_through(make_harness) -> None:
    from tests.unit.security.helpers import team_policy

    policy = team_policy(exceptions=frozenset({SecretException("docs", "docs/0.md", "github-token", "시험")}))
    harness = make_harness(policy=policy)
    result = harness.embedder.embed(index_request([TOKEN, TOKEN + " "]))  # 0번만 예외 대상 출처
    assert result.items[0].vector is not None
    assert result.items[1].failure is EmbedFailureKind.SECRET_BLOCKED


def test_query_is_checked_without_exceptions(make_harness) -> None:
    from tests.unit.security.helpers import team_policy

    policy = team_policy(exceptions=frozenset({SecretException("docs", "docs/0.md", "github-token", "시험")}))
    harness = make_harness(policy=policy)
    result = harness.embedder.embed(query_request([f"질문 {TOKEN}"]))
    assert result.items[0].failure is EmbedFailureKind.SECRET_BLOCKED
    assert harness.provider.calls == []


def test_unknown_model_is_auth_config_error(make_harness) -> None:
    request = EmbedRequest((EmbedInput("x", ("docs", "a.md")),), EmbedPurpose.INDEX, "@cf/unknown/model", "r")
    with pytest.raises(EmbedError) as excinfo:
        make_harness().embedder.embed(request)
    assert excinfo.value.kind is EmbedErrorKind.AUTH_CONFIG
