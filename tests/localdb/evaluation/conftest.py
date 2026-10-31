"""평가 대상 로컬 DB 픽스처(QK-EVL-001 tasks T001).

평가 대상은 손으로 행을 넣지 않고 실제 동기화 경로로 만든다
(`qk-dev eval-index prepare`, 가짜 자료원·가짜 임베딩 제공자).
그래야 인덱스 버전(`iv-…`), `qk.artifact.source_name`·`location`, `qk.sync_source`, 동기화 완료 시각이
운영과 같은 방식으로 채워진다. 대상은 시험 함수마다 새로 만든다. `origin` 픽스처가 시험 앞뒤로
시험 SHA가 붙은 `qk_eval_*`만 지운다. 네트워크 호출은 없다.
"""

from __future__ import annotations

import psycopg
import pytest

from qello_knowledge.adapters.postgres.eval_target import eval_target_url
from qello_knowledge.domain.keyword_rules import INDEX_BASELINE, INDEX_IDSPLIT
from tests.localdb.devtools.test_eval_index import DOCS, SHA, _prepare, _targets_factory, origin  # noqa: F401

LOCAL_ENV: dict[str, str] = {}  # 로컬 기본 포트. `DATABASE_URL`은 쓰지 않는다


def prepare_target(origin_url: str, rule: str = INDEX_BASELINE, docs=None) -> str:
    """평가 대상을 만들고 데이터베이스 이름을 돌려준다. 문서를 바꾸면 가짜 제공자로 다시 임베딩한다(외부 호출 없음).

    가짜 자료원은 원본 리비전을 `v1`로 남긴다. 실제 GitHub 자료원처럼 고정 커밋이 40자 SHA가 되도록
    시험 SHA로 바꿔 둔다.
    시험 질문 세트의 라벨 기준 커밋도 같은 SHA다.
    """
    if docs is None:
        code, data = _prepare(origin_url, rule=rule)
    else:
        code, data = _prepare(origin_url, rule=rule, targets_factory=_targets_factory(docs), allow_embed=True)
    assert code == 0, data
    name = str(data["database"])
    with psycopg.connect(eval_target_url(name, LOCAL_ENV), autocommit=True) as conn:
        conn.execute("UPDATE qk.sync_run_source SET origin_version = %s WHERE status = 'succeeded'", (SHA,))
    return name


@pytest.fixture
def baseline_target(origin: str) -> str:  # noqa: F811 - 위에서 가져온 fixture를 받는다
    return prepare_target(origin, INDEX_BASELINE)


@pytest.fixture
def idsplit_target(origin: str) -> str:  # noqa: F811
    return prepare_target(origin, INDEX_IDSPLIT)


__all__ = ["DOCS", "LOCAL_ENV", "SHA", "prepare_target"]
