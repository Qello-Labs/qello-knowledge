"""게이트 시험 도우미(QK-STO-002 tasks T027, 수집 대상 아님).

실행 기록은 QK-EVL-001 `qk-evl-001-run/v1` 계약 그대로 만들고 `write_record`로 파일에 쓴다. 질문 문장은 담지 않는다.
사례별 손 계산 값은 `tests/fixtures/gate/README.md`와 각 시험의 단언에 있다.
"""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path

from qello_knowledge.evaluation.records import (
    SCHEMA,
    CodeCommit,
    EvidenceRef,
    FilterRecord,
    LedgerRecord,
    OmittedRecord,
    QuestionRecord,
    QuestionResult,
    RunConditions,
    RunRecord,
    SetRef,
    TargetRecord,
    TopHit,
    UsageRecord,
    write_record,
)
from qello_knowledge.gate.judge import GateRequest, HistoryFacts, RecordInput
from qello_knowledge.gate.policy import parse_policy

BASE, CAND = "qk_eval_baseline_aaaaaaaaaaaa", "qk_eval_idsplit_aaaaaaaaaaaa"
V1, V2 = "iv-4c0bc4fcc642", "iv-8b7e93b22051"
BIGRAM_RULE = "TokenBigramSplitSymbol"
GOLDEN, IDENT = "golden-syn", "ident-syn"
FP_GOLDEN, FP_IDENT = "a" * 64, "b" * 64
MERGE = "m" * 40
CODE = "c" * 40
POLICY_PATH = "eval/gate_policies/syn-policy/v1.toml"


def target(name, version, *, rule="kw-index-baseline-v1", tokenizer=BIGRAM_RULE, model="@cf/baai/bge-m3"):
    return TargetRecord(name, "A", version, rule, tokenizer, model, 1024, {"docs": "r" * 40}, None, 10)


def question(qid, *, metric=True, query_form=None):
    return QuestionRecord(qid, "doc", "done", None, None, query_form, (EvidenceRef("docs", f"{qid}.md"),), metric)


def result(qid, tgt, mode, rank, *, status="ok", omitted=(), count=10, evidence=1, skipped_reason=None):
    top5 = tuple(TopHit(i, "docs", f"x{i}.md", i <= evidence) for i in range(1, 6))
    return QuestionResult(
        qid,
        tgt,
        mode,
        status,
        skipped_reason,
        tuple(OmittedRecord(o, "failed", "store_unavailable") for o in omitted),
        2,
        count,
        rank,
        top5,
        0,
        None,
    )


def record(
    set_id=GOLDEN,
    *,
    fingerprint=FP_GOLDEN,
    confirmed=True,
    targets=None,
    questions=(),
    results=(),
    modes=("hybrid",),
    run_id="evl-20261105T000000Z-00000001",
    complete=True,
    code=CODE,
    dirty=False,
    model="@cf/baai/bge-m3",
    candidates=20,
    query_rule="kw-query-v1",
):
    conditions = RunConditions(
        SetRef(set_id, 1, fingerprint, confirmed),
        {"docs": "r" * 40},
        tuple(modes),
        query_rule,
        candidates,
        60,
        FilterRecord((), ()),
        model,
        True,
        None,
        LedgerRecord("none", None, None, None, None, None, None),
        "2026-11-05T00:00:00Z",
        "2026-11-05T00:01:00Z",
        CodeCommit(code, dirty),
    )
    return RunRecord(
        SCHEMA,
        run_id,
        complete,
        None if complete else "interrupted",
        conditions,
        tuple(targets or (target(BASE, V1), target(CAND, V2, rule="kw-index-idsplit-v1"))),
        tuple(questions),
        tuple(results),
        UsageRecord(0, 0.0, 0.0, 0.0),
    )


def golden(base_ranks, cand_ranks, *, cand_status=None, base_status=None, cand_omitted=(), **kw):
    """질문 q1..qn. 랭크 목록으로 하이브리드 결과를 만든다."""
    n = len(base_ranks)
    qs = [question(f"q{i}") for i in range(1, n + 1)]
    cand_status = cand_status or {}
    base_status = base_status or {}
    rs = []
    for i, q in enumerate(qs):
        rs.append(result(q.id, BASE, "hybrid", base_ranks[i], status=base_status.get(q.id, "ok")))
        rs.append(
            result(
                q.id,
                CAND,
                "hybrid",
                cand_ranks[i],
                status=cand_status.get(q.id, "ok"),
                omitted=("vector",) if q.id in cand_omitted else (),
            )
        )
    return record(questions=qs, results=rs, **kw)


POLICY_TOML = """schema = "qk-sto-002-gate-policy/v1"
id = "syn-policy"
version = 1
mode = "hybrid"

[tokenizers]
baseline = "TokenBigramSplitSymbol"
candidate = "TokenBigramSplitSymbol"

[[sets]]
id = "golden-syn"
version = 1
fingerprint = "{fp}"
min_judged = {min_judged}
max_drop = {{ recall_at_5 = "{drop_recall}", mrr = "{drop_mrr}" }}
{extra}"""


def policy_text(*, min_judged=2, drop_recall="0", drop_mrr="0", extra=""):
    return POLICY_TOML.format(
        fp=FP_GOLDEN, min_judged=min_judged, drop_recall=drop_recall, drop_mrr=drop_mrr, extra=extra
    )


def policy(**kw):
    raw = policy_text(**kw).encode()
    import tomllib

    value, issues = parse_policy(tomllib.loads(raw.decode()), raw=raw, repo_path=POLICY_PATH)
    assert not issues, issues
    return value


def facts(records=(), **kw):
    values = dict(
        main_ref="origin/main",
        policy_merge_commit=MERGE,
        policy_matches_main=True,
        newer_policy_on_main=False,
        record_contains_policy={r.run_id: True for r in records},
        judge_commit=CODE,
        judge_dirty=False,
    )
    values.update(kw)
    return HistoryFacts(**values)


def request(*records, pol=None, baseline_version=V1, candidate_version=V2, history=None):
    inputs = tuple(RecordInput(f"runs/{i}.json", "0" * 64, r) for i, r in enumerate(records))
    return GateRequest(
        pol or policy(),
        inputs,
        BASE,
        CAND,
        baseline_version,
        candidate_version,
        history or facts(records),
    )


class FakeHistory:
    """`RepoHistory` 대역. `files`는 (참조, 경로) → 바이트."""

    def __init__(self, *, merge=MERGE, files=None, listing=(), ancestors=None, head=(CODE, False)):
        self.merge, self.files, self.listing = merge, dict(files or {}), tuple(listing)
        self.ancestors = ancestors if ancestors is not None else {CODE}
        self._head = head

    def first_added_commit(self, ref, path):
        return self.merge if (ref, path) in self.files else None

    def file_at(self, ref, path):
        return self.files.get((ref, path))

    def list_paths(self, ref, directory):
        return self.listing

    def is_ancestor(self, ancestor, commit):
        return commit in self.ancestors

    def head(self):
        return self._head


def write_repo(root: Path, *records, policy_raw: str | None = None):
    """저장소 체크아웃 흉내: 정책 파일과 실행 기록 파일을 쓰고 (정책 바이트, 실행 기록 경로들)을 돌려준다."""
    raw = (policy_raw or policy_text()).encode()
    path = root / POLICY_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(raw)
    runs = []
    for i, r in enumerate(records):
        rel = f"specs/runs/run-{i}.json"
        (root / rel).parent.mkdir(parents=True, exist_ok=True)
        write_record(replace(r, run_id=r.run_id[:-1] + str(i)), root / rel)
        runs.append(rel)
    return raw, runs
