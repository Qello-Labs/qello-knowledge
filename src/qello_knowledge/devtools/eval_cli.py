"""`qk-dev eval check|identifiers|run|tables` 조립(QK-EVL-001 contracts/cli.md).

평가 대상은 로컬 컨테이너의 `qk_eval_*` 데이터베이스뿐이다. 출력에 질문 문장, 핵심 사실, 라벨 근거 낱말, 검색어 낱말,
청크 본문, 접속 정보를 넣지 않는다. 예외는 `identifiers`가 내는 식별자와 문서 위치뿐이다(contracts/cli.md 4절).

`adapters`는 명령 안에서만 가져온다. `adapters/postgres/connection.py`가 `devtools.db`를 가져오므로 맨 위에서 가져오면
순환 가져오기가 생긴다.
"""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
from collections.abc import Callable, Mapping, Sequence
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, TextIO

from qello_knowledge.domain.embedding import MODELS, EmbedError, EmbedErrorKind
from qello_knowledge.domain.retrieval import RetrievalMode, RetrievalSettings
from qello_knowledge.domain.source_config import RetryPolicy
from qello_knowledge.domain.store import SearchFilter
from qello_knowledge.evaluation.compare import ComparisonRefused, build_comparison, render_tables
from qello_knowledge.evaluation.labeling import identifier_candidates, recompute_evidence
from qello_knowledge.evaluation.metrics import MetricSet, Ratio, metrics
from qello_knowledge.evaluation.prechecks import CostPreview, cost_preview, precheck, questions_to_embed
from qello_knowledge.evaluation.question_set import IdentifierForm, SetCheck, check_question_set
from qello_knowledge.evaluation.records import RecordError, RunRecord, new_run_id, read_record, write_record
from qello_knowledge.evaluation.reuse import CountingProvider, ReusingEmbedder
from qello_knowledge.evaluation.runner import RunRequest, run
from qello_knowledge.ports.evaluation import LedgerUnavailable, TargetUnavailable

EVAL_PREFIX = "qk_eval_"
TargetFactory = Callable[[str, Mapping[str, str]], Any]


def _emit(out: TextIO | None, as_json: bool, code: int, text: str, **values: object) -> int:
    out = out or sys.stdout  # 부를 때의 sys.stdout(시험의 출력 잡기와 맞춘다)
    if as_json:
        print(json.dumps({"exit_code": code, **values}, ensure_ascii=False, default=str), file=out)
    else:
        print(text, file=out)
    return code


def _postgres_target(name: str, source_env: Mapping[str, str]):
    from qello_knowledge.adapters.postgres.eval_target import PostgresEvalTarget

    return PostgresEvalTarget(name, source_env)


def _close(target: object) -> None:
    close = getattr(target, "close", None)
    if callable(close):
        close()


def _check_text(check: SetCheck) -> str:
    counts = check.counts
    if not check.ok:
        lines = [f"질문 세트 검사: 거부(오류 {len(check.issues)})"]
        lines += [f"  {i.question_id or '-'} {i.field} {i.rule}" for i in check.issues]
        return "\n".join(lines)
    by_type = ", ".join(f"{k} {v}" for k, v in sorted(counts.by_type.items()))
    by_label = ", ".join(f"{k} {v}" for k, v in sorted(counts.by_label.items()))
    lines = [
        f"질문 세트 검사: 통과 {check.set_id} v{check.version} sha256={check.fingerprint}",
        f"  질문 {counts.questions} (유형: {by_type}) (라벨: {by_label}) 미완료 {counts.pending}",
    ]
    lines += [f"  경고 {w.rule} {w.question_id} {' '.join(w.locations)}" for w in check.warnings]
    return "\n".join(lines)


def run_check(
    set_file: Path,
    *,
    target: str | None,
    as_json: bool,
    source_env: Mapping[str, str],
    target_factory: TargetFactory | None = None,
    out: TextIO | None = None,
) -> int:
    """contracts/cli.md 1절. 통과 0(경고가 있어도 0), 형식 오류 1, 인자 오류·파일 없음·대상 연결 실패 2."""
    if not set_file.is_file():
        return _emit(out, as_json, 2, "질문 세트 파일이 없다", error="set_not_found")
    documents = None
    if target is not None:
        if not target.startswith(EVAL_PREFIX):
            return _emit(out, as_json, 2, "평가 대상은 qk_eval_ 데이터베이스만 받는다", error="target_not_eval")
        opened = (target_factory or _postgres_target)(target, source_env)
        try:
            documents = opened.documents()
        except TargetUnavailable:
            return _emit(out, as_json, 2, "평가 대상에 연결할 수 없다", error="target_unreachable")
        finally:
            _close(opened)
    _, check = check_question_set(set_file, documents)
    code = 0 if check.ok else 1
    return _emit(out, as_json, code, _check_text(check), **check.to_dict())


def _doc(source: str, location: str) -> dict[str, str]:
    return {"source": source, "location": location}


def _identifiers_text(commits: Mapping[str, str], values: Mapping[str, Any]) -> str:
    lines = ["대상 고정 커밋: " + ", ".join(f"{k}={v}" for k, v in sorted(commits.items()))]
    if "differences" in values:
        lines.append(f"근거 문서가 다른 질문: {len(values['differences'])}")
        for diff in values["differences"]:
            missing = " ".join(d["location"] for d in diff["missing"]) or "-"
            extra = " ".join(d["location"] for d in diff["extra"]) or "-"
            lines.append(f"  {diff['question_id']} 빠진 위치 {missing} 더 있는 위치 {extra}")
        return "\n".join(lines)
    for c in values["candidates"]:
        where = " ".join(d["location"] for d in c["documents"])
        lines.append(f"  {c['form']} {c['identifier']} 문서 {len(c['documents'])} {where}")
    lines.append(f"비밀값 규칙으로 뺀 후보: {values['secret_excluded']}")
    return "\n".join(lines)


def run_identifiers(
    *,
    target: str,
    set_file: Path | None,
    forms: tuple[str, ...],
    as_json: bool,
    source_env: Mapping[str, str],
    target_factory: TargetFactory | None = None,
    out: TextIO | None = None,
) -> int:
    """contracts/cli.md 4절. 본문에서 뽑은 식별자와 문서 위치만 낸다.

    질문 문장·`label_terms`·본문 문장은 내지 않는다.
    """
    if not target.startswith(EVAL_PREFIX):
        return _emit(out, as_json, 2, "평가 대상은 qk_eval_ 데이터베이스만 받는다", error="target_not_eval")
    question_set = None
    if set_file is not None:
        if not set_file.is_file():
            return _emit(out, as_json, 2, "질문 세트 파일이 없다", error="set_not_found")
        question_set, check = check_question_set(set_file)
        if question_set is None:
            return _emit(out, as_json, 2, _check_text(check), error="set_invalid", issues=check.to_dict()["issues"])
    try:
        selected = tuple(IdentifierForm(f) for f in forms)
    except ValueError:
        return _emit(out, as_json, 2, "알 수 없는 식별자 형태", error="unknown_form")
    opened = (target_factory or _postgres_target)(target, source_env)
    try:
        commits = dict(opened.describe().commits)
        chunks = list(opened.visible_chunk_texts())
    except TargetUnavailable:
        return _emit(out, as_json, 2, "평가 대상에 연결할 수 없다", error="target_unreachable")
    finally:
        _close(opened)
    if question_set is not None:
        labels = question_set.label_commits
        if any(commits.get(name) != commit for name, commit in labels.items()):
            values = {"commits": commits, "label_commits": labels, "error": "commit_mismatch"}
            return _emit(out, as_json, 1, "대상 고정 커밋이 라벨 기준 커밋과 다르다", **values)
        diffs = [
            {
                "question_id": d.question_id,
                "missing": [_doc(*m) for m in d.missing],
                "extra": [_doc(*e) for e in d.extra],
            }
            for d in recompute_evidence(question_set, chunks)
        ]
        values = {"commits": commits, "differences": diffs}
        return _emit(out, as_json, 1 if diffs else 0, _identifiers_text(commits, values), **values)
    report = identifier_candidates(chunks, selected or None)
    candidates = [
        {
            "form": str(c.form),
            "identifier": c.identifier,
            "documents": [_doc(*d) for d in c.documents],
            "words": dict(c.word_documents),
        }
        for c in report.candidates
    ]
    values = {"commits": commits, "candidates": candidates, "secret_excluded": report.secret_excluded}
    return _emit(out, as_json, 0, _identifiers_text(commits, values), **values)


# --- run (contracts/cli.md 2절) ---

QUERY_RETRY = RetryPolicy(max_retries=1)  # 질의 경로와 같다(indexer/search_cli.py). 호출 상한도 이 값에서 계산한다


class _NoEmbedding:
    """키워드 전용 실행의 자리. 부르면 안 된다."""

    def embed(self, request):
        raise EmbedError(EmbedErrorKind.AUTH_CONFIG, "키워드 전용 실행에서 질의 임베딩을 불렀다")

    def preview(self, request):
        raise EmbedError(EmbedErrorKind.AUTH_CONFIG, "키워드 전용 실행에서 질의 임베딩을 불렀다")


class _MissingLedger:
    def today(self):
        raise LedgerUnavailable("장부 접속 정보가 비어 있다")


def _git_state() -> tuple[str | None, bool]:
    """실행 코드 커밋과 커밋하지 않은 변경 여부. `git`을 찾지 못하면 (None, True)다."""
    git = shutil.which("git")
    if git is None:
        return None, True
    try:
        sha = subprocess.run([git, "rev-parse", "HEAD"], capture_output=True, text=True, check=True).stdout.strip()  # noqa: S603
        status = subprocess.run([git, "status", "--porcelain"], capture_output=True, text=True, check=True).stdout  # noqa: S603
    except (OSError, subprocess.CalledProcessError):
        return None, True
    return sha or None, bool(status.strip())


def _postgres_ledger(url: str, query_reserve: int):
    from qello_knowledge.adapters.postgres.eval_target import PostgresDayUsageReader

    return PostgresDayUsageReader(url, query_reserve)


def _postgres_service(counter, target, budget, policy, retry):
    from qello_knowledge.adapters.postgres.eval_target import eval_target_url
    from qello_knowledge.adapters.postgres.usage import PostgresUsageLedger
    from qello_knowledge.embedding.service import EmbeddingService
    from qello_knowledge.indexer.embedding import security_outgoing_check
    from qello_knowledge.indexer.search_cli import query_retry_delay

    url = eval_target_url(target.database, target.source_env)
    return EmbeddingService(
        counter,
        target.store,
        PostgresUsageLedger(url, budget),
        budget,
        security_outgoing_check(policy),
        retry_policy=retry,
        retry_delay=query_retry_delay,
    )


def _workers_provider(source, settings):
    from qello_knowledge.indexer.sync_cli import workers_ai_provider

    return workers_ai_provider(source, settings)


def _preview_values(preview: CostPreview) -> dict[str, Any]:
    usage = preview.day_usage
    return {
        "questions": preview.questions,
        "max_calls": preview.max_calls,
        "estimated_neurons": preview.estimated_neurons,
        "usage_day": usage.usage_day.isoformat() if usage else None,
        "day_total": usage.day_total if usage else None,
        "remaining": preview.remaining,
        "query_reserve": preview.query_reserve,
    }


def _ratio(ratio: Ratio | None) -> str | None:
    return None if ratio is None else f"{ratio.fraction_text()}={ratio.text()}"


def metric_rows(record: RunRecord, values: Mapping[tuple[str, str], MetricSet]) -> list[dict[str, Any]]:
    """대상별·방식별 지표 요약(분자/분모=값). 실행 출력과 기록으로 다시 계산한 값이 같은지 시험이 비교한다."""
    candidates = {t.database: t.candidate for t in record.targets}
    rows = []
    for (target, mode), m in values.items():
        rows.append(
            {
                "target": target,
                "candidate": candidates.get(target),
                "mode": mode,
                "recall_at_5": _ratio(m.recall_at_5),
                "mrr": _ratio(m.mrr),
                "top20": _ratio(m.top20),
                "precision_at_5": _ratio(m.precision_at_5),
                "mean_results": _ratio(m.mean_results),
                "cap_hit": _ratio(m.cap_hit),
                "excluded": dict(m.excluded),
                "failures": dict(m.failures),
                "omitted": dict(m.omitted),
                "zero_terms": m.zero_terms,
            }
        )
    return rows


def _run_text(record: RunRecord, rows: Sequence[Mapping[str, Any]], out_path: Path) -> str:
    state = "완료" if record.complete else f"미완료({record.stop_reason})"
    lines = [f"평가 실행: {state} {record.run_id} 기록 {out_path}"]
    lines.append(f"  제공자 호출 {record.usage.provider_calls}, Neurons {record.usage.neurons:.6f}")
    for row in rows:
        lines.append(
            f"  {row['target']}({row['candidate']}) {row['mode']} Recall@5 {row['recall_at_5']} MRR {row['mrr']}"
            f" 상위20 {row['top20']}"
        )
    return "\n".join(lines)


def _settings(args: argparse.Namespace) -> RetrievalSettings:
    overrides = {
        k: v
        for k, v in (("query_rule", args.query_rule), ("candidates", args.candidates), ("rrf_k", args.rrf_k))
        if v is not None
    }
    return RetrievalSettings().with_overrides(overrides) if overrides else RetrievalSettings()


def run_eval(
    args: argparse.Namespace,
    source_env: Mapping[str, str],
    *,
    target_factory: TargetFactory | None = None,
    ledger_factory: Callable[[str, int], Any] | None = None,
    provider_factory: Callable[[Mapping[str, str], Any], Any] | None = None,
    service_factory: Callable[..., Any] | None = None,
    git_state: Callable[[], tuple[str | None, bool]] | None = None,
    clock: Callable[[], datetime] | None = None,
    out: TextIO | None = None,
) -> int:
    """contracts/cli.md 2절. 순서: 인자 → 설정 → 세트 → 대상 → 정책 → 비용 관문 → 실행 → 기록 쓰기 → 요약."""
    as_json = args.json
    targets: list[str] = list(dict.fromkeys(args.target))
    modes = tuple(RetrievalMode(m) for m in (args.mode or [m.value for m in RetrievalMode]))
    needs_embedding = any(m is not RetrievalMode.KEYWORD for m in modes)
    usage_target = args.usage_target or targets[0]

    def fail(code: int, error: str, text: str, **values: object) -> int:
        return _emit(out, as_json, code, f"평가 실행: 멈춤 {error} {text}".strip(), error=error, **values)

    if args.allow_query_embedding and args.max_neurons is None:
        return fail(2, "max_neurons_required", "--allow-query-embedding에는 --max-neurons가 필요하다")
    if args.max_neurons is not None and args.max_neurons < 0:
        return fail(2, "max_neurons_invalid", "")
    if usage_target not in targets:
        return fail(2, "usage_target_not_in_targets", "")
    if needs_embedding and not args.ledger_url_env:
        return fail(2, "ledger_url_env_required", "임베딩이 드는 방식에는 --ledger-url-env가 필요하다")
    if args.out.exists() and not args.out.is_dir():
        return fail(2, "out_exists", "실행 기록 경로가 이미 있다")
    if not args.out.is_dir() and not args.out.parent.is_dir():
        return fail(2, "out_dir_missing", "실행 기록을 둘 디렉터리가 없다")
    try:
        settings = _settings(args)
    except (ValueError, TypeError):
        return fail(2, "settings_out_of_range", "")
    from qello_knowledge.config.check import budget_settings, build_report
    from qello_knowledge.config.loader import load
    from qello_knowledge.config.registry import Entrypoint

    config = load(Entrypoint.INDEX, environ=source_env, env_file=None)
    budget = budget_settings(config)
    if not build_report(config).ok or budget is None:
        return fail(2, "config_invalid", "설정 점검 실패(qk-index config check)")
    if not args.set_file.is_file():
        return fail(2, "set_not_found", "")
    question_set, check = check_question_set(args.set_file)
    if question_set is None:
        return fail(1, "set_invalid", "", issues=check.to_dict()["issues"])
    for name in targets:
        if not name.startswith(EVAL_PREFIX):
            return fail(1, "target_not_eval", name, target=name)
    factory = target_factory or _postgres_target
    opened = {name: factory(name, source_env) for name in targets}
    try:
        checked = precheck(question_set, list(opened.items()))
        if not checked.ok:
            return fail(1, checked.reason or "precheck_failed", checked.target or "", target=checked.target)
        policy = None
        if needs_embedding:
            from qello_knowledge.security.policy import load_policy
            from qello_knowledge.sources.config import load_sources

            configs, issues = load_sources(args.sources)
            policy, policy_issues = load_policy(args.exceptions, configs) if not issues else (None, issues)
            if issues or policy_issues or policy is None:
                return fail(2, "policy_invalid", "자료원 설정·보안 예외 파일 오류")
        model = MODELS.get(checked.targets[0].description.embedding_model or "")
        if needs_embedding and model is None:
            return fail(1, "model_mismatch", "", target=checked.targets[0].name)
        ledger = None
        production = False
        if needs_embedding:
            from qello_knowledge.adapters.postgres.eval_target import ledger_is_production

            conninfo = (source_env.get(args.ledger_url_env) or "").strip()
            if not conninfo:
                ledger, production = _MissingLedger(), True
            else:
                production = ledger_is_production(conninfo, source_env, targets)
                if production and args.allow_remote_read:
                    ledger = (ledger_factory or _postgres_ledger)(conninfo, budget.query_reserve)
        embed_questions = questions_to_embed(question_set, checked.targets)
        preview = cost_preview(
            embed_questions,
            QUERY_RETRY,
            model or MODELS["@cf/baai/bge-m3"],
            ledger,
            needs_embedding=needs_embedding,
            ledger_is_production=production,
            allow_remote_read=args.allow_remote_read,
            allow_query_embedding=args.allow_query_embedding,
            max_neurons=args.max_neurons,
            daily_allowance=budget.daily_allowance,
        )
        _close(ledger)
        if preview.blocked_reason is not None:
            code = 3 if preview.blocked_reason == "remote_read_not_allowed" else 4
            values = _preview_values(preview)
            text = " ".join(f"{k}={v}" for k, v in values.items())
            return fail(code, preview.blocked_reason, text, preview=values)
        counter = None
        embedder = ReusingEmbedder(_NoEmbedding())
        if needs_embedding:
            counter = CountingProvider((provider_factory or _workers_provider)(source_env, config))
            usage = _UsageTarget(usage_target, opened[usage_target], source_env)
            service = (service_factory or _postgres_service)(counter, usage, budget, policy, QUERY_RETRY)
            embedder = ReusingEmbedder(service)
        request = RunRequest(
            question_set=question_set,
            targets=tuple(targets),
            modes=modes,
            settings=settings,
            filters=SearchFilter(tuple(args.source_kind), tuple(args.artifact_kind)),
            usage_target=usage_target if needs_embedding else None,  # 키워드 전용은 사용량을 기록하지 않는다
            retry=QUERY_RETRY,
            allow_query_embedding=args.allow_query_embedding,
            max_neurons=args.max_neurons,
            allow_remote_read=args.allow_remote_read,
        )
        now = clock or (lambda: datetime.now(UTC))
        run_id = new_run_id(now())
        out_path = args.out / f"{run_id}.json" if args.out.is_dir() else args.out  # 디렉터리면 실행 ID로 이름을 짓는다
        record = run(
            request,
            checked.targets,
            {name: target.store for name, target in opened.items()},
            embedder,
            counter,
            preview=preview,
            clock=now,
            run_id=run_id,
            code_commit=(git_state or _git_state)(),
        )
    finally:
        for target in opened.values():
            _close(target)
    usage_values = dict(record.usage.__dict__)
    try:
        write_record(record, out_path)
    except FileExistsError:
        return fail(2, "out_exists", "실행 기록 경로가 이미 있다", run_id=record.run_id, usage=usage_values)
    except OSError:
        # 검색·질의 임베딩은 이미 끝났다. 호출 수는 출력에라도 남긴다
        return fail(2, "record_write_failed", "실행 기록을 쓰지 못했다", run_id=record.run_id, usage=usage_values)
    rows = metric_rows(record, metrics(record))
    code = 0 if record.complete else 5
    return _emit(
        out,
        as_json,
        code,
        _run_text(record, rows, out_path),
        run_id=record.run_id,
        complete=record.complete,
        stop_reason=record.stop_reason,
        record=str(out_path),
        usage=usage_values,
        metrics=rows,
    )


class _UsageTarget:
    """사용량을 기록할 대상. 임베딩 서비스 조립에 이름·저장소·로컬 주소 재료만 넘긴다."""

    def __init__(self, database: str, target: Any, source_env: Mapping[str, str]) -> None:
        self.database = database
        self.store = target.store
        self.source_env = source_env


# --- tables (contracts/cli.md 3절) ---


def run_tables(args: argparse.Namespace, *, out: TextIO | None = None) -> int:
    """실행 기록에서 Markdown 표를 낸다. 저장소·외부 호출 없음. 비교 조건 불일치·미완료 기록 1, 인자·스키마 오류 2."""
    as_json = args.json
    try:
        records = [read_record(path) for path in args.run]
    except RecordError:
        return _emit(out, as_json, 2, "실행 기록을 읽을 수 없거나 계약과 다르다", error="record_invalid")
    run_ids = [r.run_id for r in records]
    if len(set(run_ids)) != len(run_ids):
        return _emit(out, as_json, 2, "같은 실행 기록을 두 번 받았다", error="duplicate_run")
    targets = list(dict.fromkeys(args.target)) or None
    known = {t.database for r in records for t in r.targets}
    if targets and not set(targets) <= known:
        return _emit(out, as_json, 2, "기록에 없는 대상", error="target_not_in_records")
    if targets and any(not {t.database for t in r.targets} & set(targets) for r in records):
        return _emit(out, as_json, 2, "고른 대상이 하나도 없는 실행 기록이 있다", error="target_not_in_record")
    try:
        table = build_comparison(records, targets)
    except ComparisonRefused as refused:
        if refused.incomplete:
            text = "미완료 기록은 비교하지 않는다: " + ", ".join(refused.incomplete)
            return _emit(out, as_json, 1, text, error="incomplete_record", runs=list(refused.incomplete))
        mismatches = [
            {"item": m.item, "values": [{"run_id": run_id, "value": value} for run_id, value in m.values]}
            for m in refused.mismatches
        ]
        lines = ["비교 조건이 다르다:"] + [
            f"  {m['item']}: " + ", ".join(f"{v['run_id']}={v['value']}" for v in m["values"]) for m in mismatches
        ]
        return _emit(out, as_json, 1, "\n".join(lines), error="condition_mismatch", mismatches=mismatches)
    try:
        text = render_tables(table, breakdowns=tuple(dict.fromkeys(args.breakdown)))
    except (TypeError, ValueError, KeyError):
        return _emit(out, as_json, 2, "실행 기록 값의 형식이 계약과 다르다", error="record_invalid")
    if as_json:
        return _emit(out, True, 0, "", markdown=text)
    (out or sys.stdout).write(text)
    return 0


__all__ = ["metric_rows", "run_check", "run_eval", "run_identifiers", "run_tables"]
