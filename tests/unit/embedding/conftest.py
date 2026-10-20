"""임베딩 단위 시험 공통 fixture."""

from __future__ import annotations

from collections.abc import Callable

import pytest

from tests.unit.embedding.helpers import Harness, build_harness


@pytest.fixture
def make_harness() -> Callable[..., Harness]:
    return build_harness
