"""실행 순서, 근거 미색인, 질문별 실패, 실행 멈춤(QK-EVL-001 spec US3-3~US3-9, research R-08, tasks T021).

가짜 `RetrievalStore`는 정해 둔 결과를 돌려준다. 청크 n의 출처 URL은 `https://example.invalid/doc-n`이다.
"""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path

import pytest

from qello_knowledge.domain.embedding import ProviderFailureKind
from qello_knowledge.domain.retrieval import RetrievalMode
from qello_knowledge.domain.store import StoreError, StoreUnavailable
from qello_knowledge.embedding.fake import FakeEmbeddingProvider
from qello_knowledge.evaluation.prechecks import Candidate, CostPreview, PreparedTarget
from qello_knowledge.evaluation.question_set import QuestionSet, check_question_set
from qello_knowledge.evaluation.runner import RunRequest, run
from qello_knowledge.ports.embedder import ProviderFailure
from tests.unit.evaluation.fakes import GOLDEN, description, document, question_set_file, reusing_service
from tests.unit.retrieval.fakes import FakeRetrievalStore, keyword_result, vector_result

A = document("docs/A.md", "https://example.invalid/doc-1")
B = document("docs/B.md", "https://example.invalid/doc-2")
OTHER = document("docs/C.md", "https://example.invalid/doc-3")
NOW = datetime(2026, 10, 31, 9, 0, tzinfo=UTC)
PREVIEW = CostPreview(
    questions=2, max_calls=4, estimated_neurons=0.01, day_usage=None, remaining=None, query_reserve=None
)
ALL_MODES = (RetrievalMode.VECTOR, RetrievalMode.HYBRID, RetrievalMode.KEYWORD)


@pytest.fixture
def golden(tmp_path: Path) -> QuestionSet:
    question_set, _ = check_question_set(question_set_file(tmp_path, "fixture-golden", 1, GOLDEN.read_text("utf-8")))
    assert question_set is not None
    return question_set


def _store(**kwargs) -> FakeRetrievalStore:
    kwargs.setdefault("vector", vector_result(2, 1, 3))
    kwargs.setdefault("keyword", keyword_result((1, 1), (3, 1)))
    return FakeRetrievalStore(**kwargs)


def _target(name: str, docs=(A, B, OTHER), candidate: Candidate = Candidate.A) -> PreparedTarget:
    return PreparedTarget(name, description(name, index_version="v1"), tuple(docs), candidate)


def _run(golden: QuestionSet, targets, stores, provider=None, modes=ALL_MODES):
    embedder, counter = reusing_service(provider)
    request = RunRequest(
        question_set=golden, targets=tuple(t.name for t in targets), modes=modes, usage_target=targets[0].name
    )
    record = run(
        request,
        targets,
        stores,
        embedder,
        counter,
        preview=PREVIEW,
        clock=lambda: NOW,
        run_id="evl-20261031T090000Z-0000abcd",
        code_commit=("c" * 40, False),
    )
    return record, counter


def test_order_and_result_count(golden: QuestionSet) -> None:
    targets = [_target("qk_eval_a"), _target("qk_eval_b", candidate=Candidate.B)]
    stores = {t.name: _store() for t in targets}
    record, counter = _run(golden, targets, stores)
    assert record.complete and record.stop_reason is None
    assert [(r.question, r.target, r.mode) for r in record.results] == [
        (q, t, m) for q in ("g01", "g02") for t in ("qk_eval_a", "qk_eval_b") for m in ("vector", "hybrid", "keyword")
    ]
    assert counter.calls == 2  # 질문마다 한 번
    assert all("chunk_context" not in s.names() for s in stores.values())  # 순위만 받는다
    assert [q.metric_target for q in record.questions] == [True, True, False, False]
    assert record.usage.provider_calls == 2


def test_first_evidence_rank_top5_and_digest(golden: QuestionSet) -> None:
    targets = [_target("qk_eval_a")]
    record, _ = _run(golden, targets, {"qk_eval_a": _store()}, modes=(RetrievalMode.VECTOR,))
    g01, g02 = record.results
    assert g01.status == "ok" and g01.result_count == 3
    assert g01.first_evidence_rank == 2 and g02.first_evidence_rank == 1  # 청크 2가 docs/B.md
    assert [(h.rank, h.location, h.evidence) for h in g01.top5] == [
        (1, "docs/B.md", False),
        (2, "docs/A.md", True),
        (3, "docs/C.md", False),
    ]
    rows = [
        [1, "dnd-backend-docs", "docs/B.md"],
        [2, "dnd-backend-docs", "docs/A.md"],
        [3, "dnd-backend-docs", "docs/C.md"],
    ]
    expected = hashlib.sha256(json.dumps(rows, ensure_ascii=False, separators=(",", ":")).encode("utf-8")).hexdigest()
    assert g01.result_digest == expected and g01.unindexed_evidence == 0


def test_unindexed_in_one_target_is_skipped_there(golden: QuestionSet) -> None:
    targets = [_target("qk_eval_a"), _target("qk_eval_b", docs=(A, OTHER))]
    without_b = _store(vector=vector_result(1, 3))  # 노출 문서만 결과로 나온다
    record, counter = _run(golden, targets, {"qk_eval_a": _store(), "qk_eval_b": without_b})
    assert record.complete
    skipped = [(r.question, r.target, r.mode) for r in record.results if r.status == "skipped"]
    assert skipped == [("g02", "qk_eval_b", m) for m in ("vector", "hybrid", "keyword")]
    assert {r.skipped_reason for r in record.results if r.status == "skipped"} == {"evidence_unindexed"}
    assert all(r.unindexed_evidence == 1 and r.result_digest is None for r in record.results if r.status == "skipped")
    assert counter.calls == 2


def test_unindexed_everywhere_is_not_embedded(golden: QuestionSet) -> None:
    targets = [_target("qk_eval_a", docs=(A, OTHER))]
    record, counter = _run(golden, targets, {"qk_eval_a": _store(vector=vector_result(1, 3))})
    assert [r.status for r in record.results if r.question == "g02"] == ["skipped"] * 3
    assert counter.calls == 1 and record.complete
    assert len(record.results) == 2 * 1 * 3


def test_partly_unindexed_counts_missing_evidence(tmp_path: Path) -> None:
    text = GOLDEN.read_text("utf-8").replace(
        'location = "docs/A.md" }]',
        'location = "docs/A.md" }, { source = "dnd-backend-docs", location = "docs/Z.md" }]',
    )
    question_set, _ = check_question_set(question_set_file(tmp_path, "fixture-golden", 1, text))
    assert question_set is not None
    record, _ = _run(question_set, [_target("qk_eval_a")], {"qk_eval_a": _store()}, modes=(RetrievalMode.KEYWORD,))
    assert record.results[0].unindexed_evidence == 1 and record.results[0].status == "ok"


def test_question_failures_are_recorded_without_fallback(golden: QuestionSet) -> None:
    store = _store(fail={"search_keyword_terms": StoreError("x")})
    record, _ = _run(golden, [_target("qk_eval_a")], {"qk_eval_a": store})
    by_mode = {r.mode: r for r in record.results if r.question == "g01"}
    assert by_mode["keyword"].status == "keyword_search_failed" and by_mode["keyword"].result_count == 0
    assert by_mode["hybrid"].status == "ok"
    assert [(o.search, o.reason) for o in by_mode["hybrid"].omitted] == [("keyword", "keyword_search_failed")]
    assert record.complete


def test_vector_only_embedding_failure_is_a_question_failure(golden: QuestionSet) -> None:
    bad = ProviderFailure(ProviderFailureKind.BAD_RESPONSE)
    provider = FakeEmbeddingProvider(fail_calls={1: bad})
    record, _ = _run(golden, [_target("qk_eval_a")], {"qk_eval_a": _store()}, provider=provider)
    g01 = {r.mode: r for r in record.results if r.question == "g01"}
    assert g01["vector"].status == "query_embedding_failed"
    assert [(o.search, o.reason, o.detail) for o in g01["hybrid"].omitted] == [
        ("vector", "query_embedding_failed", "bad_response")
    ]
    assert record.complete


@pytest.mark.parametrize(
    ("provider", "store", "reason"),
    [
        (
            FakeEmbeddingProvider(fail_calls={1: ProviderFailure(ProviderFailureKind.PROVIDER_QUOTA)}),
            None,
            "provider_quota",
        ),
        (
            FakeEmbeddingProvider(fail_calls={1: ProviderFailure(ProviderFailureKind.AUTH_CONFIG)}),
            None,
            "query_embedding_unavailable",
        ),
        (
            None,
            {"fail": {"search_vector": StoreUnavailable("x"), "search_keyword_terms": StoreUnavailable("x")}},
            "store_unavailable",
        ),
        (
            None,
            {"vector": vector_result(version=None), "keyword": keyword_result(version=None)},
            "index_version_changed",
        ),
        (
            None,
            {"vector": vector_result(1, version="v2"), "keyword": keyword_result((1, 1), version="v2")},
            "index_version_changed",
        ),
        (None, {"vector": vector_result(9), "keyword": keyword_result((9, 1))}, "index_version_changed"),
        (None, {"fail": {"search_vector": KeyboardInterrupt()}}, "interrupted"),
    ],
    ids=["quota", "embed_error", "store", "no_active_index", "version", "unknown_url", "interrupt"],
)
def test_stops_mark_record_incomplete(golden: QuestionSet, provider, store, reason: str) -> None:
    stores = {"qk_eval_a": _store(**(store or {}))}
    record, _ = _run(golden, [_target("qk_eval_a")], stores, provider=provider)
    assert not record.complete and record.stop_reason == reason
    assert record.results == ()  # 멈춘 질문의 결과는 남기지 않는다


def test_stop_keeps_finished_questions(golden: QuestionSet) -> None:
    quota = ProviderFailure(ProviderFailureKind.PROVIDER_QUOTA)
    provider = FakeEmbeddingProvider(fail_calls={2: quota})
    record, _ = _run(golden, [_target("qk_eval_a")], {"qk_eval_a": _store()}, provider=provider)
    assert record.stop_reason == "provider_quota"
    assert {r.question for r in record.results} == {"g01"} and len(record.results) == 3


def test_keyword_only_does_not_embed(golden: QuestionSet) -> None:
    record, counter = _run(golden, [_target("qk_eval_a")], {"qk_eval_a": _store()}, modes=(RetrievalMode.KEYWORD,))
    assert counter.calls == 0 and [r.mode for r in record.results] == ["keyword", "keyword"]
    assert record.results[0].keyword_terms > 0


def test_conditions_and_targets(golden: QuestionSet) -> None:
    record, _ = _run(golden, [_target("qk_eval_a")], {"qk_eval_a": _store()})
    conditions = record.conditions
    assert conditions.question_set == ("fixture-golden", 1, golden.fingerprint, False)
    assert conditions.label_commits == {"dnd-backend-docs": "0" * 39 + "1"}
    assert conditions.modes == ("vector", "hybrid", "keyword")
    assert (conditions.query_rule, conditions.candidates, conditions.rrf_k) == ("kw-query-v1", 20, 60)
    assert conditions.usage_target == "qk_eval_a" and conditions.query_vector_reuse
    assert conditions.code_commit == ("c" * 40, False)
    assert record.targets[0].candidate == "A" and record.targets[0].documents == 3
