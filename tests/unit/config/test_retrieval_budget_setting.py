"""`QK_RETRIEVAL_CONTEXT_BUDGET` 범위 검사(QK-RET-001 research R-12, tasks T014)."""

from __future__ import annotations

import pytest

from qello_knowledge.config.registry import SETTINGS, Entrypoint

SPEC = next(s for s in SETTINGS if s.name == "QK_RETRIEVAL_CONTEXT_BUDGET")


@pytest.mark.parametrize("value", ["1", "9", "2000", "7999", "8000"])
def test_accepts_range(value: str) -> None:
    assert SPEC.rule(value)


@pytest.mark.parametrize("value", ["0", "8001", "9000", "-1", "1.5", "", "02000", "abc"])
def test_rejects_out_of_range(value: str) -> None:
    assert not SPEC.rule(value)


def test_default_and_entrypoints() -> None:
    assert SPEC.default == "3000" and not SPEC.secret and not SPEC.required
    assert SPEC.entrypoints == {Entrypoint.QUERY, Entrypoint.INDEX}
