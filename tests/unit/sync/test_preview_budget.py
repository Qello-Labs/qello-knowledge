from qello_knowledge.domain.embedding import BudgetSettings
from qello_knowledge.sync.plan import plan_source
from qello_knowledge.sync.preview import preview
from qello_knowledge.sync.run import SyncOptions, current_spec, run_sync
from tests.unit.sync.helpers import DEFAULT_DOCS, harness


def plans(h, options):
    spec = current_spec(h.deps)
    return tuple(plan_source(t, h.deps, h.store.load_documents(t.source_kind), spec.id, options) for t in h.targets)


def test_preview_does_not_write_or_embed_and_uses_same_target_sets():
    first = harness()
    run_sync(first.targets, first.deps, SyncOptions())
    docs = {k: v for k, v in DEFAULT_DOCS.items() if k != "D"}
    docs["B"] = "# Changed B"
    for options in (SyncOptions(), SyncOptions(confirm_takedown=True, allow_partial_budget=True)):
        h = harness(docs, store=first.store)
        before = h.store.writes
        source_plans = plans(h, options)
        result = preview(
            source_plans, h.deps.embedder, h.deps.chunking_settings.model_version, h.store.index_state(), options
        )
        assert h.store.writes == before and h.provider.calls == []
        assert result.embedding_preview.to_embed == 1
        assert result.runnable
    actual = harness(docs, store=first.store)
    run = run_sync(actual.targets, actual.deps, SyncOptions())
    assert run.sources[0]["counts"] == {"PROCESS": 1, "UNCHANGED": 3, "TAKE_DOWN": 1}


def test_global_budget_hold_keeps_security_takedown_and_seen_updates():
    first = harness()
    run_sync(first.targets, first.deps, SyncOptions())
    h = harness(
        {**DEFAULT_DOCS, "A": "# Changed A"},
        store=first.store,
        settings=BudgetSettings(index_budget=0),
        access={"D": None},
    )
    result = run_sync(h.targets, h.deps, SyncOptions())
    assert result.status == "stopped" and result.exit_code == 5
    assert h.provider.calls == []
    assert h.store.load_documents("fake")["D"].status == "deleted"
    assert result.sources[0]["counts"] == {"HOLD": 1, "UNCHANGED": 3, "TAKE_DOWN": 1}


def test_preview_estimate_and_basis_are_embedder_results():
    from qello_knowledge.domain.embedding import EmbedInput, EmbedPurpose, EmbedRequest

    h = harness()
    source_plans = plans(h, SyncOptions())
    pieces = tuple(
        EmbedInput(d.embedding_text, (p.source_name, doc.chunked.screened.content.location))
        for p in source_plans
        for doc in p.decisions
        if doc.chunked
        for d in doc.chunked.drafts
    )
    expected = h.deps.embedder.preview(
        EmbedRequest(pieces, EmbedPurpose.INDEX, h.deps.chunking_settings.model_version, "preview")
    )
    got = preview(
        source_plans, h.deps.embedder, h.deps.chunking_settings.model_version, h.store.index_state(), SyncOptions()
    )
    assert got.embedding_preview == expected


def test_budget_preview_and_run_agree_on_held_targets():
    h = harness(settings=BudgetSettings(index_budget=0))
    result = preview(
        plans(h, SyncOptions()),
        h.deps.embedder,
        h.deps.chunking_settings.model_version,
        h.store.index_state(),
        SyncOptions(),
    )
    assert result.sources[0]["counts"] == {"HOLD": 5}
    assert result.sources[0]["holds"] == ["BUDGET_EXCEEDED"]


def test_two_sources_are_budgeted_together_and_partial_option_stays_within_budget():
    from dataclasses import replace

    from qello_knowledge.security.kinds import KINDS
    from qello_knowledge.security.policy import SecurityPolicy
    from tests.unit.security.helpers import fake_config

    text = "# Synthetic\n\n" + "word " * 400
    first = harness({"A": text}, settings=BudgetSettings(index_budget=1))
    second = harness(
        {"B": text + "second"},
        store=first.store,
        settings=BudgetSettings(index_budget=1),
        config=fake_config(name="other"),
    )
    second.targets[0].adapter.kind = "fake_two"
    target = replace(
        second.targets[0], source_kind="fake_two", config=replace(second.targets[0].config, kind="fake_two")
    )
    policy = SecurityPolicy(kinds={**KINDS, "fake_two": replace(KINDS["fake"], kind="fake_two")})
    deps = replace(first.deps, policy=policy)
    result = run_sync((*first.targets, target), deps, SyncOptions())
    assert result.status == "stopped" and first.provider.calls == []
    assert [source["counts"] for source in result.sources] == [{"HOLD": 1}, {"HOLD": 1}]
    assert first.store.documents == {}
    partial = harness({"A": text, "B": text + "second"}, settings=BudgetSettings(index_budget=1))
    result = run_sync(partial.targets, partial.deps, SyncOptions(allow_partial_budget=True))
    assert result.status == "stopped"
    assert len(partial.store.documents) == 1 and len(partial.provider.calls) == 1
    assert partial.ledger.today().index_used <= 1
