"""`qk-dev eval identifiers`(QK-EVL-001 contracts/cli.md 4절, research R-13, tasks T015).

형태별 식별자를 담은 합성 문서로 후보 A 대상을 만든다(가짜 자료원·가짜 임베딩 제공자, 외부 호출 없음).
"""

from __future__ import annotations

import io
import json
from pathlib import Path

import pytest

from qello_knowledge.adapters.postgres.eval_target import PostgresEvalTarget
from qello_knowledge.devtools.eval_cli import run_identifiers
from tests.localdb.evaluation.conftest import LOCAL_ENV, SHA, prepare_target
from tests.unit.evaluation.fakes import IDENTIFIERS, question_set_file

pytestmark = pytest.mark.localdb

DOCS = {
    "A": "# 결제\n\n`retryPayment` 함수가 실패한 결제를 다시 시도한다.\n정책은 `RetryPolicy`, 호출은 `HTTPClient`.\n",
    "B": (
        "# 배포\n\n금요일에는 배포하지 않는다.\n"
        "설정 `max_retries`, 규칙 `kw-index-baseline-v1`.\n경로 `/api/v1/users`.\n"
    ),
}


def _run(target: str, **kwargs) -> tuple[int, dict]:
    out = io.StringIO()
    code = run_identifiers(target=target, as_json=True, source_env=LOCAL_ENV, out=out, **kwargs)
    return code, json.loads(out.getvalue())


def _commit(target: str) -> str:
    with PostgresEvalTarget(target, LOCAL_ENV) as opened:
        return opened.describe().commits["dnd-backend-docs"]


def test_lists_candidates_without_body_sentences(origin: str) -> None:
    target = prepare_target(origin, docs=DOCS)
    code, data = _run(target, set_file=None, forms=())
    assert code == 0
    assert data["commits"] == {"dnd-backend-docs": _commit(target)}
    found = {(c["form"], c["identifier"]): c["documents"] for c in data["candidates"]}
    assert found[("camel", "retryPayment")] == [{"source": "dnd-backend-docs", "location": "docs/A.md"}]
    assert ("url_path", "/api/v1/users") in found and ("kebab", "kw-index-baseline-v1") in found
    assert data["secret_excluded"] == 0
    text = json.dumps(data, ensure_ascii=False)
    assert "다시 시도한다" not in text and "배포하지 않는다" not in text


def _set_file(tmp_path: Path, commit: str) -> Path:
    text = IDENTIFIERS.read_text(encoding="utf-8").replace("0" * 39 + "1", commit)
    return question_set_file(tmp_path, "fixture-identifiers", 1, text)


def test_target_commit_is_test_sha(origin: str) -> None:
    assert _commit(prepare_target(origin, docs=DOCS)) == SHA


def test_set_with_matching_evidence_exits_0(origin: str, tmp_path: Path) -> None:
    target = prepare_target(origin, docs=DOCS)
    code, data = _run(target, set_file=_set_file(tmp_path, _commit(target)), forms=())
    assert code == 0 and data["differences"] == []
    assert "retryPayment" not in json.dumps(data) and "금요일" not in json.dumps(data, ensure_ascii=False)


def test_set_with_other_evidence_exits_1(origin: str, tmp_path: Path) -> None:
    docs = {**DOCS, "C": "# 재시도\n\n`retryPayment`를 여기서도 부른다.\n"}
    target = prepare_target(origin, docs=docs)
    code, data = _run(target, set_file=_set_file(tmp_path, _commit(target)), forms=())
    assert code == 1
    assert {d["question_id"] for d in data["differences"]} == {"camel-01-original", "camel-01-partial"}
    assert data["differences"][0]["missing"] == [{"source": "dnd-backend-docs", "location": "docs/C.md"}]


def test_set_with_other_label_commit_exits_1(origin: str, tmp_path: Path) -> None:
    target = prepare_target(origin, docs=DOCS)
    code, data = _run(target, set_file=_set_file(tmp_path, "f" * 40), forms=())
    assert code == 1 and data["error"] == "commit_mismatch"


def test_bad_target_names_and_missing_target_exit_2() -> None:
    assert _run("postgres", set_file=None, forms=())[0] == 2
    code, data = _run("qk_eval_missing_000000000000", set_file=None, forms=())
    assert code == 2 and data["error"] == "target_unreachable"
