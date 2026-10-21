"""합성 자료원·재생 전송·가짜 임베딩만 조립한다."""

from types import SimpleNamespace
from urllib.parse import quote

from qello_knowledge.adapters.fake import FakeSourceAdapter
from qello_knowledge.adapters.replay import ReplayTransport
from qello_knowledge.domain.chunking import ChunkingSettings
from qello_knowledge.domain.embedding import BudgetSettings
from qello_knowledge.embedding.fake import FakeEmbeddingProvider
from qello_knowledge.embedding.service import EmbeddingService
from qello_knowledge.security.policy import SecurityPolicy
from qello_knowledge.security.send_gate import OutgoingPiece, check_outgoing
from qello_knowledge.sources.session import DefaultSourceSession
from tests.unit.fakes import InMemoryUsageLedger
from tests.unit.security.helpers import FakeClock, fake_config
from tests.unit.sync.fake_store import MemorySyncStore

_REPLAY_SEND = ReplayTransport.send

DEFAULT_DOCS = {letter: f"# Synthetic {letter}\n\nText for {letter}.\n" for letter in "ABCDE"}


def harness(
    docs=None,
    *,
    store=None,
    cache_store=None,
    config=None,
    version="v1",
    titles=None,
    locations=None,
    access=None,
    origin=None,
    provider=None,
    ledger=None,
    settings=None,
    chunking=None,
):
    from qello_knowledge.sync.plan import SyncTarget
    from qello_knowledge.sync.run import SyncDependencies

    docs = DEFAULT_DOCS if docs is None else docs
    config = config or fake_config()
    titles, locations, access = titles or {}, locations or {}, access or {}
    items, exchanges = [], []
    for identity, text in docs.items():
        location = locations.get(identity, f"docs/{identity}.md")
        title = titles.get(identity)
        items.append(
            dict(
                id=identity,
                url=f"https://fake.invalid/view/{quote(identity, safe='')}",
                version=version,
                modified_at=None,
                item_type="markdown_file",
                title=title,
                location=location,
                size_bytes=None,
                access=access.get(identity, {"visibility": "public"}),
                origin_state="ACTIVE",
            )
        )
        exchanges.append(
            dict(
                method="GET",
                url="https://fake.invalid/items/" + quote(identity, safe=""),
                responses=[
                    dict(
                        status=200,
                        headers={},
                        body=dict(
                            body=text, content_format="MARKDOWN", version=version, location=location, title=title
                        ),
                    )
                ],
            )
        )
    raw_origin = (
        origin if origin is not None else dict(origin_id="repo-1", origin_name="synthetic/docs", version=version)
    )
    exchanges.insert(
        0,
        dict(
            method="GET",
            url="https://fake.invalid/items?cursor=",
            responses=[dict(status=200, headers={}, body=dict(items=items, next_cursor=None, origin=raw_origin))],
        ),
    )
    transport = ReplayTransport(exchanges)
    adapter = FakeSourceAdapter()
    clock = FakeClock()
    session = DefaultSourceSession(transport, adapter, config, clock)
    store = store or MemorySyncStore()
    cache_store = cache_store or store
    provider = provider or FakeEmbeddingProvider()
    settings = settings or BudgetSettings()
    ledger = ledger or InMemoryUsageLedger(settings)
    policy = SecurityPolicy()
    embedder = EmbeddingService(
        provider,
        cache_store,
        ledger,
        settings,
        lambda text, origin: check_outgoing((OutgoingPiece(text, origin),), policy).hits,
        sleep=lambda seconds: None,
    )
    deps = SyncDependencies(
        store=store,
        cache_store=cache_store,
        embedder=embedder,
        policy=policy,
        chunking_settings=chunking or ChunkingSettings(),
        clock=clock,
    )
    target = SyncTarget(config.name, config.kind, config=config, adapter=adapter, session=session)
    return SimpleNamespace(
        targets=(target,), deps=deps, store=store, provider=provider, ledger=ledger, transport=transport
    )


def cli_factory(**kwargs):
    """기존 CLI 정상 run 시험도 같은 실제 흐름에 가짜 의존성을 주입한다."""
    from dataclasses import replace
    from pathlib import Path

    h = harness()
    targets = []
    for config in kwargs["configs"]:
        if config.enabled:
            one = harness(store=h.store, cache_store=h.store, config=config)
            one.transport = ReplayTransport.from_file(Path("tests/fixtures/sync/responses.json"))
            one.targets = (
                replace(
                    one.targets[0],
                    session=DefaultSourceSession(one.transport, one.targets[0].adapter, config, one.deps.clock),
                ),
            )
            one.transport.send = _REPLAY_SEND.__get__(one.transport, type(one.transport))
            targets.extend(one.targets)
    return SimpleNamespace(targets=tuple(targets), deps=replace(h.deps, policy=kwargs["policy"]), close=lambda: None)
