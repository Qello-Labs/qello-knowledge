"""`qk-dev eval-index prepare` 인자 검사(QK-RET-001 contracts/cli.md 2절). DB에 연결하지 않는 경로만 본다."""

from __future__ import annotations

import io
import json

import pytest

from qello_knowledge.devtools.eval_index import eval_db_name, prepare


@pytest.mark.parametrize("commit", ["abc1234", "main", "G" * 40, "0" * 41, ""])
def test_rejects_non_sha_commit_before_touching_db(commit: str) -> None:
    out = io.StringIO()
    assert prepare(rule="kw-index-idsplit-v1", commit=commit, source_env={}, settings=None, out=out) == 2
    assert json.loads(out.getvalue())["error"] == "commit_must_be_full_sha"


def test_rejects_unknown_rule() -> None:
    assert prepare(rule="kw-index-v9", commit="0" * 40, source_env={}, settings=None, out=io.StringIO()) == 2


def test_names() -> None:
    sha = "abcdef0123456789" + "0" * 24
    assert eval_db_name("kw-index-baseline-v1", sha) == "qk_eval_baseline_abcdef012345"
    assert eval_db_name("kw-index-idsplit-v1", sha) == "qk_eval_idsplit_abcdef012345"
