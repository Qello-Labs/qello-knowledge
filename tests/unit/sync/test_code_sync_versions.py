"""코드 청킹 동기화 연결: 문서별 버전, 인덱스 버전, 재계획(QK-CHK-001 research R-09·R-10, spec US6-4, tasks T027).

공용 도우미(`helpers.py`)는 Markdown만 만들므로 코드 자료용 조립은 이 파일 안에 둔다. 외부 호출이 없다.
"""

from types import SimpleNamespace
from urllib.parse import quote

from qello_knowledge.adapters.fake import FakeSourceAdapter
from qello_knowledge.adapters.replay import ReplayTransport
from qello_knowledge.chunking.code.version import code_chunking_version
from qello_knowledge.chunking.version import chunking_version, index_chunking_version, version_for
from qello_knowledge.domain.chunking import ChunkingSettings, CodeChunkingSettings
from qello_knowledge.domain.embedding import BudgetSettings
from qello_knowledge.domain.source import ContentFormat
from qello_knowledge.domain.source_config import SourceScope
from qello_knowledge.embedding.fake import FakeEmbeddingProvider
from qello_knowledge.embedding.service import EmbeddingService
from qello_knowledge.ports.sync import IndexSpec
from qello_knowledge.security.policy import SecurityPolicy
from qello_knowledge.security.send_gate import OutgoingPiece, check_outgoing
from qello_knowledge.sources.session import DefaultSourceSession
from qello_knowledge.sync.plan import SyncTarget, plan_source
from qello_knowledge.sync.run import SyncDependencies, SyncOptions, current_spec, run_sync
from tests.unit.chunking.helpers import screened
from tests.unit.fakes import InMemoryUsageLedger
from tests.unit.security.helpers import FakeClock, fake_config
from tests.unit.sync.fake_store import MemorySyncStore

JAVA = "package a;\n\nclass A {\n    void f() {\n        g();\n    }\n}\n"
MARKDOWN = "# 문서\n\n본문 줄\n"
DOCS = {"code-a": ("A.java", JAVA), "doc-b": ("b.md", MARKDOWN), "code-empty": ("Empty.java", "")}


def code_harness(docs, *, code=None, store=None):
    """코드 자료를 섞은 합성 자료원. 전송 직전 검사에 넘어간 텍스트를 `sent`에 기록한다."""
    config = fake_config(scope=SourceScope(("**/*.md", "**/*.java", "**/*.kt")))
    items, exchanges = [], []
    for identity, (name, text) in docs.items():
        code_file = name.endswith((".java", ".kt"))
        location = f"src/main/java/a/{name}" if code_file else f"docs/{name}"
        items.append(
            dict(
                id=identity,
                url=f"https://fake.invalid/view/{quote(identity, safe='')}",
                version="v1",
                modified_at=None,
                item_type="code_file" if code_file else "markdown_file",
                title=None,
                location=location,
                size_bytes=None,
                access={"visibility": "public"},
                origin_state="ACTIVE",
            )
        )
        body = dict(
            body=text,
            content_format="CODE" if code_file else "MARKDOWN",
            version="v1",
            location=location,
            title=None,
        )
        exchanges.append(
            dict(
                method="GET",
                url="https://fake.invalid/items/" + quote(identity, safe=""),
                responses=[dict(status=200, headers={}, body=body)],
            )
        )
    origin = dict(origin_id="repo-1", origin_name="synthetic/code", version="v1")
    exchanges.insert(
        0,
        dict(
            method="GET",
            url="https://fake.invalid/items?cursor=",
            responses=[dict(status=200, headers={}, body=dict(items=items, next_cursor=None, origin=origin))],
        ),
    )
    transport, adapter, clock = ReplayTransport(exchanges), FakeSourceAdapter(), FakeClock()
    store = store or MemorySyncStore()
    policy, sent = SecurityPolicy(), []

    def outgoing(text, source):
        sent.append(text)
        return check_outgoing((OutgoingPiece(text, source),), policy).hits

    settings = BudgetSettings()
    provider = FakeEmbeddingProvider()
    embedder = EmbeddingService(
        provider, store, InMemoryUsageLedger(settings), settings, outgoing, sleep=lambda seconds: None
    )
    deps = SyncDependencies(store, store, embedder, policy, ChunkingSettings(), clock, code_chunking=code)
    target = SyncTarget(
        config.name,
        config.kind,
        config=config,
        adapter=adapter,
        session=DefaultSourceSession(transport, adapter, config, clock),
    )
    return SimpleNamespace(targets=(target,), deps=deps, store=store, sent=sent, provider=provider)


def plan_again(h):
    spec = current_spec(h.deps)
    target = h.targets[0]
    return plan_source(target, h.deps, h.store.load_documents(target.source_kind), spec.id, SyncOptions())


def test_version_for_picks_the_responsible_chunker():
    settings, code = ChunkingSettings(), CodeChunkingSettings()
    java = screened(JAVA, content_format="CODE", location="A.java").content
    markdown = screened(MARKDOWN, location="a.md").content
    python = screened("x = 1\n", content_format="CODE", location="a.py").content
    assert version_for(java, settings, code) == code_chunking_version(code, settings)
    assert version_for(markdown, settings, code) == chunking_version(settings)
    assert version_for(python, settings, code) == chunking_version(settings)
    assert version_for(java, settings) == chunking_version(settings)


def test_positional_dependencies_keep_code_chunking_off():
    deps = SyncDependencies(None, None, None, None, ChunkingSettings(), None)
    assert deps.code_chunking is None


def test_current_spec_off_and_on():
    off = code_harness(DOCS)
    assert current_spec(off.deps) == IndexSpec(
        "iv-4c0bc4fcc642", "@cf/baai/bge-m3", 1024, "chk-md-20d966f730bb", "meta-v1"
    )
    on = current_spec(code_harness(DOCS, code=CodeChunkingSettings()).deps)
    assert on.id != "iv-4c0bc4fcc642"
    assert on.metadata_schema_version == "meta-v2"
    assert "+chk-code-" in on.chunking_version


def test_on_replan_without_changes_processes_nothing():
    h = code_harness(DOCS, code=CodeChunkingSettings())
    result = run_sync(h.targets, h.deps, SyncOptions())
    assert result.sources[0]["counts"] == {"PROCESS": 3}
    assert {doc.source_id for doc in h.store.documents.values()} >= set(DOCS)
    again = plan_again(code_harness(DOCS, code=CodeChunkingSettings(), store=h.store))
    assert [d.change_reason for d in again.decisions if d.change_reason] == []
    assert again.chunking_summary.chunking_version == ""


def test_off_keeps_code_documents_not_target():
    h = code_harness(DOCS)
    plan = plan_again(h)
    by_id = {d.source_id: d for d in plan.decisions}
    assert by_id["code-a"].chunked is None and by_id["doc-b"].chunked is not None
    assert plan.chunking_summary.chunking_version == "chk-md-20d966f730bb"
    assert plan.chunking_summary.code_chunking_version is None


def test_summary_version_does_not_depend_on_first_document():
    code = CodeChunkingSettings()
    code_first = plan_again(code_harness(DOCS, code=code)).chunking_summary
    markdown_first = plan_again(code_harness(dict(reversed(DOCS.items())), code=code)).chunking_summary
    expected = index_chunking_version(ChunkingSettings(), code)
    assert code_first.chunking_version == markdown_first.chunking_version == expected
    assert code_first.code_chunking_version == code_chunking_version(code, ChunkingSettings())


def test_content_format_is_code():
    plan = plan_again(code_harness({"code-a": ("A.java", JAVA)}, code=CodeChunkingSettings()))
    [decision] = plan.decisions
    assert decision.chunked.screened.content.content_format == ContentFormat.CODE
