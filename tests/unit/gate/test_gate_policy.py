"""게이트 정책 형식(QK-STO-002 contracts/gate-policy.md)."""

import tomllib
from fractions import Fraction

import pytest

from qello_knowledge.gate.policy import load_policy, parse_policy
from tests.unit.gate.gate_builders import POLICY_PATH, policy_text

EXAMPLE = """schema = "qk-sto-002-gate-policy/v1"
id = "kw-index-idsplit-rollout"
version = 1
mode = "hybrid"

[tokenizers]
baseline = "TokenBigramSplitSymbol"
candidate = "TokenBigramSplitSymbol"

[search]
query_rule = "kw-query-v1"
candidates = 20
rrf_k = 60

[[sets]]
id = "qk-evl-001-golden"
version = 2
fingerprint = "0000"
min_judged = 20
max_drop = { recall_at_5 = "0", mrr = "0.02" }

[[sets]]
id = "qk-evl-001-identifiers"
version = 1
fingerprint = "1111"
min_judged = 60
max_drop = { recall_at_5 = "0.0125", mrr = "0.02" }

[[guardrails]]
kind = "G1"
set = "qk-evl-001-golden"
limit = "0"

[[guardrails]]
kind = "G2"
set = "qk-evl-001-identifiers"
mode = "keyword"
limit = "0"

[[guardrails]]
kind = "G3"
set = "qk-evl-001-identifiers"
limit = "0.0125"
"""
EXAMPLE_PATH = "eval/gate_policies/kw-index-idsplit-rollout/v1.toml"


def _parse(text, path=POLICY_PATH):
    return parse_policy(tomllib.loads(text), raw=text.encode(), repo_path=path)


def test_contract_example_parses():
    policy, issues = _parse(EXAMPLE, EXAMPLE_PATH)
    assert issues == ()
    assert policy.mode == "hybrid" and len(policy.sets) == 2
    assert policy.sets[1].max_drop == {"recall_at_5": Fraction(1, 80), "mrr": Fraction(1, 50)}
    assert [(g.kind, g.mode) for g in policy.guardrails] == [("G1", "hybrid"), ("G2", "keyword"), ("G3", "keyword")]
    assert policy.search == {"query_rule": "kw-query-v1", "candidates": 20, "rrf_k": 60}
    assert len(policy.sha256) == 64


def test_search_defaults_come_from_retrieval_settings():
    policy, issues = _parse(policy_text())
    assert issues == () and policy.search == {"query_rule": "kw-query-v1", "candidates": 20, "rrf_k": 60}


@pytest.mark.parametrize(
    ("change", "expected"),
    [
        (lambda t: t.replace('schema = "qk-sto-002-gate-policy/v1"', 'schema = "other"'), "policy_schema"),
        (lambda t: t.replace('id = "syn-policy"', 'id = "Bad ID"'), "policy_id"),
        (lambda t: t.replace("version = 1\nmode", "version = 0\nmode"), "policy_version"),
        (lambda t: t.replace('mode = "hybrid"', 'mode = "other"'), "policy_mode"),
        (lambda t: t.replace('mrr = "0"', 'mrr = "-0.1"'), "policy_number"),
        (lambda t: t.replace('mrr = "0"', 'mrr = "1e-2"'), "policy_number"),
        (lambda t: t.replace('mrr = "0"', 'mrr = ""'), "policy_number"),
        (lambda t: t.replace("min_judged = 2", "min_judged = 0"), "policy_min_judged"),
        (lambda t: t + "\nsurprise = 1\n", "policy_unknown_key"),
        (lambda t: t.replace('candidate = "TokenBigramSplitSymbol"', 'candidate = ""'), "policy_tokenizer"),
        (lambda t: t + "\n[search]\ncandidates = 0\n", "policy_search"),
        (
            lambda t: (
                t + '\n[[sets]]\nid = "golden-syn"\nversion = 1\nfingerprint = "x"\nmin_judged = 1\n'
                'max_drop = { recall_at_5 = "0", mrr = "0" }\n'
            ),
            "policy_set_duplicate",
        ),
        (lambda t: t + '\n[[guardrails]]\nkind = "G9"\nset = "golden-syn"\nlimit = "0"\n', "policy_guardrail_kind"),
        (lambda t: t + '\n[[guardrails]]\nkind = "G1"\nset = "nope"\nlimit = "0"\n', "policy_guardrail_set"),
        (
            lambda t: t + '\n[[guardrails]]\nkind = "G3"\nset = "golden-syn"\nmode = "hybrid"\nlimit = "0"\n',
            "policy_guardrail_mode",
        ),
    ],
)
def test_validation_issues(change, expected):
    policy, issues = _parse(change(policy_text()))
    assert policy is None and expected in issues


def test_no_sets_and_path_version():
    text = policy_text().split("[[sets]]")[0]
    assert "policy_no_sets" in _parse(text)[1]
    assert "policy_path_version" in _parse(policy_text(), "eval/gate_policies/syn-policy/v2.toml")[1]
    assert "policy_id" in _parse(policy_text(), "eval/gate_policies/other/v1.toml")[1]


def test_invalid_toml_and_fingerprint(tmp_path):
    bad = tmp_path / "v1.toml"
    bad.write_text("schema = ", encoding="utf-8")
    assert load_policy(bad) == (None, ("policy_toml_invalid",))
    good = tmp_path / "syn-policy" / "v1.toml"
    good.parent.mkdir()
    good.write_text(policy_text(), encoding="utf-8")
    first, _ = load_policy(good, repo_path=POLICY_PATH)
    good.write_text(policy_text(min_judged=3), encoding="utf-8")
    second, _ = load_policy(good, repo_path=POLICY_PATH)
    assert first.sha256 != second.sha256 and first.path == POLICY_PATH
