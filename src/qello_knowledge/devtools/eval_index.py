"""`qk-dev eval-index prepare`: ADR-010 비교용 평가 색인을 별도 로컬 데이터베이스에 만든다.

QK-RET-001 research R-09, spec FR-029.

- 대상은 언제나 로컬 컨테이너다. 접속 정보는 `DATABASE_URL`이 아니라 로컬 기본 주소와 데이터베이스 이름으로 만든다.
- 임베딩 캐시는 원본 데이터베이스에서 읽기 전용으로 복사한다. 원본에는 쓰지 않는다.
- 자료원 설정과 범위 검토 파일은 임시 사본에서만 `ref`를 커밋 SHA로 바꾼다. 저장소 파일은 그대로다.
- 준비 중에는 `<이름>__preparing`을 쓰고 성공하면 최종 이름으로 바꾼다.
  지우는 대상은 그 준비용 이름뿐이다(AGENTS.md 4절).
- `--keyword-tokenizer`(QK-EVL-001 후보 C, research R-12)는 같은 커밋의 후보 A 데이터베이스를 템플릿으로 복제하고
  키워드 색인 토크나이저만 바꾼다. 동기화·임베딩·원본 호출이 없다. 옵션이 없으면 위 동작 그대로다.
"""

from __future__ import annotations

import io
import json
import re
import shutil
import sys
import tempfile
from collections.abc import Callable, Mapping
from pathlib import Path
from typing import TextIO

import psycopg

from qello_knowledge.adapters.postgres.connection import database_url, with_database
from qello_knowledge.adapters.postgres.migrate import apply_migrations, load_migrations
from qello_knowledge.domain.chunking import ChunkingSettings
from qello_knowledge.domain.keyword_rules import INDEX_BASELINE, INDEX_IDSPLIT, INDEX_RULES

PREPARING_SUFFIX = "__preparing"
SHORT_NAMES = {INDEX_BASELINE: "baseline", INDEX_IDSPLIT: "idsplit"}
_SHA = re.compile(r"[0-9a-f]{40}")
_REF_LINE = re.compile(r'^(\s*ref\s*=\s*)"[^"\n]*"', re.M)
_MODEL = "@cf/baai/bge-m3"


def eval_db_name(rule: str, commit: str) -> str:
    return f"qk_eval_{SHORT_NAMES[rule]}_{commit[:12]}"


TOKENIZER_NAMES = {"TokenBigramSplitSymbolAlpha": "alpha"}  # 후보 C(QK-EVL-001 contracts/cli.md 5절)
KEYWORD_INDEX = "chunk_search_text_pgroonga"


def eval_tokenizer_db_name(commit: str, tokenizer: str = "TokenBigramSplitSymbolAlpha") -> str:
    return f"qk_eval_baseline_{TOKENIZER_NAMES[tokenizer]}_{commit[:12]}"


def _pin_source_ref(text: str, name: str, commit: str) -> str | None:
    """`[[source]]` 묶음 중 `name`인 것의 `ref`만 바꾼다. 찾지 못하면 None."""
    starts = [m.start() for m in re.finditer(r"^\[\[source\]\]", text, re.M)] + [len(text)]
    for begin, end in zip(starts, starts[1:], strict=False):
        block = text[begin:end]
        if re.search(rf'^\s*name\s*=\s*"{re.escape(name)}"\s*$', block, re.M) and _REF_LINE.search(block):
            return text[:begin] + _REF_LINE.sub(rf'\g<1>"{commit}"', block, count=1) + text[end:]
    return None


def _pinned_config(sources_path: Path, reviews_dir: Path, name: str, commit: str, workdir: Path):
    sources = _pin_source_ref(sources_path.read_text(encoding="utf-8"), name, commit)
    review_file = reviews_dir / f"{name}.toml"
    if sources is None or not review_file.is_file():
        return None
    review_text = review_file.read_text(encoding="utf-8")
    if not _REF_LINE.search(review_text):
        return None
    reviews = workdir / "source_reviews"
    shutil.copytree(reviews_dir, reviews)
    (reviews / f"{name}.toml").write_text(_REF_LINE.sub(rf'\g<1>"{commit}"', review_text, count=1), encoding="utf-8")
    pinned = workdir / "sources.toml"
    pinned.write_text(sources, encoding="utf-8")
    return pinned, reviews


def _exists(admin: str, name: str) -> bool:
    with psycopg.connect(admin, autocommit=True) as conn:
        return conn.execute("SELECT 1 FROM pg_database WHERE datname = %s", (name,)).fetchone() is not None


def _copy_embeddings(origin: str, target: str) -> int:
    with psycopg.connect(origin) as src, psycopg.connect(target, autocommit=True) as dst:
        src.read_only = True
        rows = src.execute(
            "SELECT input_hash, model_version, vector::text FROM qk.embedding WHERE model_version = %s ORDER BY id",
            (_MODEL,),
        ).fetchall()
        with dst.cursor() as cur:
            cur.executemany(
                "INSERT INTO qk.embedding (input_hash, model_version, vector) VALUES (%s, %s, %s::vector)"
                " ON CONFLICT (input_hash, model_version) DO NOTHING",
                rows,
            )
    return len(rows)


def _plans(runtime, options):
    from qello_knowledge.sync.identity import select_targets
    from qello_knowledge.sync.plan import plan_source
    from qello_knowledge.sync.run import current_spec

    deps = runtime.deps
    spec = current_spec(deps)
    targets = select_targets(runtime.targets, deps.store.load_sources(), options.source)
    plans = tuple(plan_source(t, deps, deps.store.load_documents(t.source_kind), spec.id, options) for t in targets)
    return plans, spec


def prepare(
    *,
    rule: str,
    commit: str,
    source_env: Mapping[str, str],
    settings,
    source_name: str = "dnd-backend-docs",
    from_url_env: str = "DATABASE_URL",
    sources_path: Path = Path("config/sources.toml"),
    reviews_dir: Path = Path("config/source_reviews"),
    exceptions_path: Path = Path("config/security_exceptions.toml"),
    allow_embed: bool = False,
    policy=None,
    targets_factory: Callable | None = None,
    provider_factory: Callable | None = None,
    out: TextIO = sys.stdout,
) -> int:
    """research R-09 1~8단계. 종료 코드는 contracts/cli.md 2절. `policy`·`*_factory`는 시험용 주입 자리다."""
    from qello_knowledge.indexer.sync_cli import build_runtime
    from qello_knowledge.security.policy import load_policy
    from qello_knowledge.sources.scope_review import load_checked_sources
    from qello_knowledge.sync.activate import activate_first_index
    from qello_knowledge.sync.preview import preview
    from qello_knowledge.sync.run import SyncOptions, run_sync

    def emit(code: int, **values: object) -> int:
        print(json.dumps({"exit_code": code, **values}, ensure_ascii=False, default=str), file=out)
        return code

    if rule not in INDEX_RULES:
        return emit(2, error="unknown_rule")
    if not _SHA.fullmatch(commit):
        return emit(2, error="commit_must_be_full_sha")
    origin = (source_env.get(from_url_env) or "").strip() or database_url(source_env)
    admin = database_url({k: v for k, v in source_env.items() if k == "QK_LOCAL_DB_PORT"})  # 로컬 컨테이너
    final = eval_db_name(rule, commit)
    preparing = final + PREPARING_SUFFIX
    if _exists(admin, final):
        return emit(5, error="database_exists", database=final)
    with psycopg.connect(admin, autocommit=True) as conn:
        conn.execute(f'DROP DATABASE IF EXISTS "{preparing}" WITH (FORCE)')  # 이전 실패의 준비용 잔여물만
        conn.execute(f'CREATE DATABASE "{preparing}"')
    target = with_database(admin, preparing)
    stage = "migrate"
    try:
        with psycopg.connect(target, autocommit=True) as conn:
            if apply_migrations(conn, load_migrations(), is_local=True, out=io.StringIO()) != 0:
                return emit(1, stage=stage)
        stage = "copy_cache"
        copied = _copy_embeddings(origin, target)
        stage = "sources"
        with tempfile.TemporaryDirectory(prefix="qk-eval-") as tmp:
            pinned = _pinned_config(sources_path, reviews_dir, source_name, commit, Path(tmp))
            if pinned is None:
                return emit(1, stage=stage, error="ref_not_found")
            configs, issues = load_checked_sources(*pinned)
        if issues:
            return emit(1, stage=stage, error="source_review_invalid")
        if policy is None:
            policy, issues = load_policy(exceptions_path, configs)
            if issues:
                return emit(1, stage=stage, error="security_policy_invalid")
        chunking = ChunkingSettings(keyword_text_rule=rule)
        options = SyncOptions(trigger="manual", target="local", source=source_name)
        build = dict(
            settings=settings,
            configs=configs,
            policy=policy,
            source={**source_env, "DATABASE_URL": target},
            chunking=chunking,
            targets_factory=targets_factory,
            provider_factory=provider_factory,
        )
        stage = "preview"
        runtime = build_runtime(**build)
        try:
            plans, spec = _plans(runtime, options)
            estimate = preview(
                plans, runtime.deps.embedder, spec.embedding_model, runtime.deps.store.index_state(), options
            )
        finally:
            runtime.close()
        neurons = estimate.embedding_preview.estimated_neurons
        if neurons > 0 and not allow_embed:
            return emit(4, stage=stage, estimated_neurons=neurons, database=preparing)
        stage = "sync"
        runtime = build_runtime(**build)
        try:
            result = run_sync(runtime.targets, runtime.deps, options)
            if result.exit_code != 0:
                return emit(1, stage=stage, sync_status=result.status)
            stage = "activate"
            check = activate_first_index(runtime.deps.store, spec.id)
            if check.failed_conditions:
                return emit(1, stage=stage, failed_conditions=list(check.failed_conditions))
        finally:
            runtime.close()
        with psycopg.connect(target, autocommit=True) as conn:
            calls, used = conn.execute(
                "SELECT count(*), coalesce(sum(coalesce(neurons, estimated_neurons)), 0) FROM qk.embedding_usage"
            ).fetchone()
        stage = "rename"
        with psycopg.connect(admin, autocommit=True) as conn:
            conn.execute(f'ALTER DATABASE "{preparing}" RENAME TO "{final}"')
    except (psycopg.Error, OSError) as exc:
        return emit(1, stage=stage, error=type(exc).__name__)
    return emit(
        0,
        database=final,
        rule=rule,
        commit=commit,
        index_version=spec.id,
        copied_vectors=copied,
        embedding_calls=int(calls),
        neurons=float(used),
        estimated_neurons=neurons,
    )


def _tokenizer_of(conn: psycopg.Connection) -> str | None:
    row = conn.execute(
        "SELECT c.reloptions FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace"
        " WHERE n.nspname = 'qk' AND c.relname = %s",
        (KEYWORD_INDEX,),
    ).fetchone()
    for option in (row[0] if row else None) or ():
        key, _, value = option.partition("=")
        if key.strip() == "tokenizer":
            return value.strip().strip("'\"")
    return None


def _uses_keyword_index(conn: psycopg.Connection) -> bool:
    """`qk.search_keyword_terms`와 같은 설정(`enable_seqscan = off`)에서 `&@~` 조건이 그 색인을 쓰는지."""
    with conn.transaction():
        conn.execute("SET LOCAL enable_seqscan = off")
        plan = conn.execute("EXPLAIN SELECT id FROM qk.chunk WHERE search_text &@~ %s", ("payment",)).fetchall()
    return any(KEYWORD_INDEX in str(line[0]) for line in plan)


def prepare_tokenizer(*, commit: str, tokenizer: str, source_env: Mapping[str, str], out: TextIO | None = None) -> int:
    """후보 C 평가 대상(QK-EVL-001 research R-12). 종료 코드는 QK-EVL-001 contracts/cli.md 5절.

    1. 기준(후보 A)·최종 이름 확인
    2. `__preparing`만 지우고 `STRATEGY = FILE_COPY`로 복제(PGroonga는 데이터베이스 디렉터리에 자기 파일을 둔다)
    3. 한 트랜잭션에서 키워드 색인을 같은 이름·같은 열·바꾼 토크나이저로 다시 만들기
    4. 토크나이저 값과 `EXPLAIN` 색인 사용 확인
    5. 최종 이름으로 바꾸기
    """
    out = out or sys.stdout

    def emit(code: int, **values: object) -> int:
        print(json.dumps({"exit_code": code, **values}, ensure_ascii=False, default=str), file=out)
        return code

    if tokenizer not in TOKENIZER_NAMES:
        return emit(2, error="unknown_tokenizer")
    if not _SHA.fullmatch(commit):
        return emit(2, error="commit_must_be_full_sha")
    admin = database_url({k: v for k, v in source_env.items() if k == "QK_LOCAL_DB_PORT"})  # 로컬 컨테이너
    base = eval_db_name(INDEX_BASELINE, commit)
    final = eval_tokenizer_db_name(commit, tokenizer)
    preparing = final + PREPARING_SUFFIX
    if _exists(admin, final):
        return emit(5, error="database_exists", database=final)
    if not _exists(admin, base):
        return emit(6, error="base_database_missing", base_database=base)
    stage = "clone"
    try:
        with psycopg.connect(admin, autocommit=True) as conn:
            conn.execute(f'DROP DATABASE IF EXISTS "{preparing}" WITH (FORCE)')  # 이전 실패의 준비용 잔여물만
            conn.execute(f'CREATE DATABASE "{preparing}" TEMPLATE "{base}" STRATEGY = FILE_COPY')
        target = with_database(admin, preparing)
        stage = "reindex"
        with psycopg.connect(target) as conn, conn.transaction():
            conn.execute(f"DROP INDEX qk.{KEYWORD_INDEX}")
            conn.execute(
                f"CREATE INDEX {KEYWORD_INDEX} ON qk.chunk USING pgroonga (search_text)"
                f" WITH (tokenizer = '{tokenizer}')"
            )
        stage = "verify"
        with psycopg.connect(target) as conn:
            found = _tokenizer_of(conn)
            used = _uses_keyword_index(conn)
            row = conn.execute("SELECT id FROM qk.index_version WHERE status = 'active'").fetchone()
        if found != tokenizer or not used:
            return emit(1, stage=stage, tokenizer=found, index_used=used, database=preparing)
        stage = "rename"
        with psycopg.connect(admin, autocommit=True) as conn:
            conn.execute(f'ALTER DATABASE "{preparing}" RENAME TO "{final}"')
    except (psycopg.Error, OSError) as exc:
        return emit(1, stage=stage, error=type(exc).__name__)
    return emit(
        0,
        base_database=base,
        database=final,
        tokenizer=tokenizer,
        index_version=row[0] if row else None,
        external_calls=0,
    )
