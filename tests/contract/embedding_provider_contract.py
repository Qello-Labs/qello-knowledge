"""제공자 계약 묶음(contracts/embedder.md "제공자 계약 테스트" 1~5). 어떤 `EmbeddingProvider`든 이 묶음을 통과한다.

각 구현의 시험 파일이 `ProviderCase`로 사례별 제공자를 만들어 넘긴다.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

import pytest

from qello_knowledge.domain.embedding import MODELS, ProviderFailureKind
from qello_knowledge.ports.embedder import EmbeddingProvider, ProviderFailure

MODEL = MODELS["@cf/baai/bge-m3"]
TEXTS = ("첫째 문단", "second paragraph")


@dataclass(frozen=True)
class ProviderCase:
    """사례 이름 → 그 사례를 재현하는 제공자. 이름은 ok, too_long, quota, transient, unauthorized."""

    make: Callable[[str], EmbeddingProvider]
    secrets: tuple[str, ...] = ()  # 예외 문구에 나오면 안 되는 문자열
    deterministic: bool = True


def check_vectors_match_inputs(case: ProviderCase) -> None:
    batch = case.make("ok").embed_texts(MODEL, TEXTS)
    assert len(batch.vectors) == len(TEXTS)
    assert all(len(v) == MODEL.dimension for v in batch.vectors)


def check_same_input_same_output(case: ProviderCase) -> None:
    first = case.make("ok").embed_texts(MODEL, TEXTS)
    second = case.make("ok").embed_texts(MODEL, TEXTS)
    assert first == second


def _failure(case: ProviderCase, name: str) -> ProviderFailure:
    with pytest.raises(ProviderFailure) as excinfo:
        case.make(name).embed_texts(MODEL, TEXTS)
    message = str(excinfo.value) + repr(excinfo.value)
    assert all(secret not in message for secret in case.secrets)
    assert all(text not in message for text in TEXTS)
    return excinfo.value


def check_input_too_long(case: ProviderCase) -> None:
    assert _failure(case, "too_long").kind is ProviderFailureKind.INPUT_TOO_LONG


def check_quota_and_transient(case: ProviderCase) -> None:
    assert _failure(case, "quota").kind is ProviderFailureKind.PROVIDER_QUOTA
    assert _failure(case, "transient").kind is ProviderFailureKind.TRANSIENT


def check_auth_failure_hides_secrets(case: ProviderCase) -> None:
    assert _failure(case, "unauthorized").kind is ProviderFailureKind.AUTH_CONFIG


CHECKS = (
    check_vectors_match_inputs,
    check_same_input_same_output,
    check_input_too_long,
    check_quota_and_transient,
    check_auth_failure_hides_secrets,
)
