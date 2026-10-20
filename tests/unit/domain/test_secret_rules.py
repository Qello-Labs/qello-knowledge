"""비밀값 규칙. 토큰 형식 값은 파일에 그대로 남지 않게 실행 중에 이어 붙여 만든다(research R-12)."""

import ast
from pathlib import Path

import pytest

from qello_knowledge.domain import secret_rules
from qello_knowledge.domain.secret_rules import REQUIRED_KINDS, RULES, SecretHit, find_secrets
from tests.unit.synthetic_secrets import SYNTHETIC

BASE_RULES = (
    "private-key",
    "aws-access-key",
    "github-token",
    "slack-token",
    "anthropic-key",
    "openai-key",
    "notion-token",
    "figma-token",
    "atlassian-token",
    "db-url-with-password",
    "assigned-secret",
    "env-assigned-secret",
)

BASE_SAMPLES = {
    "private-key": "-----BEGIN " + "RSA PRIVATE KEY-----",
    "aws-access-key": "AK" + "IA" + "A" * 16,
    "github-token": "gh" + "p_" + "A" * 36,
    "slack-token": "xo" + "xb-" + "1" * 24,
    "anthropic-key": "sk-" + "ant-" + "a" * 30,
    "openai-key": "sk-" + "proj-" + "a" * 40,
    "notion-token": "nt" + "n_" + "a" * 44,
    "figma-token": "fi" + "gd_" + "a" * 36,
    "atlassian-token": "ATA" + "TT" + "a" * 30,
    "db-url-with-password": "postgres" + "ql://user:" + "s3cretvalue" + "@db.example:5432/app",
    "assigned-secret": 'api_key = "' + "q" * 24 + '"',
    "env-assigned-secret": "API_" + "KEY=" + "q" * 24,
}


def test_base_rules_are_kept():
    names = [rule.name for rule in RULES]
    assert set(BASE_RULES) <= set(names)
    assert len(names) == len(set(names))


@pytest.mark.parametrize("name", BASE_RULES)
def test_each_base_rule_matches_a_synthetic_value(name):
    hits = find_secrets("intro\n" + BASE_SAMPLES[name] + "\n")
    assert SecretHit(name, 2) in hits


def test_hits_carry_only_rule_and_line():
    hits = find_secrets(BASE_SAMPLES["github-token"])
    assert hits == (SecretHit("github-token", 1),)
    assert all(BASE_SAMPLES["github-token"] not in repr(hit) for hit in hits)


def test_skip_rules_are_not_reported():
    assert find_secrets(BASE_SAMPLES["github-token"], skip=frozenset({"github-token"})) == ()


def test_module_parses_as_python_312():
    source = Path(secret_rules.__file__).read_text(encoding="utf-8")
    ast.parse(source, feature_version=(3, 12))


# --- 반드시 잡을 종류 (FR-009, SC-001) ---

NAMES = ("GITHUB_TOKEN", "DISCORD_BOT_TOKEN", "SERVICE_SECRET", "DB_PASSWORD", "OPENAI_API_KEY")
VALUE = "q" * 24


def test_required_kinds_cover_the_synthetic_samples():
    assert set(REQUIRED_KINDS) == set(SYNTHETIC)
    names = {rule.name for rule in RULES}
    assert all(rules and set(rules) <= names for rules in REQUIRED_KINDS.values())
    assert len(RULES) == 16


@pytest.mark.parametrize("kind", sorted(SYNTHETIC))
def test_required_kind_is_detected(kind):
    hits = find_secrets("intro\n" + SYNTHETIC[kind])
    assert {hit.rule for hit in hits} & set(REQUIRED_KINDS[kind])


@pytest.mark.parametrize("name", NAMES)
@pytest.mark.parametrize(
    "template",
    ['{name} = "{value}"', "{lower}: '{value}'", "{name}={value}", 'export {name}="{value}"'],
)
def test_name_rules_catch_quoted_and_env_assignments(name, template):
    line = template.format(name=name, lower=name.lower(), value=VALUE)
    assert find_secrets(line), "required name rule missed an assignment"


@pytest.mark.parametrize(
    "line",
    [
        "GITHUB_TOKEN=${GITHUB_TOKEN}",
        'GITHUB_TOKEN="<github-token>"',
        'token: "example-token-value-123"',
        "DB_PASSWORD=changeme-please-123",
        'api_key = "redacted-xxxxxxxxxxxx"',
        "token = settings.github_token",
        "max_tokens: 4096",
    ],
)
def test_placeholders_and_references_are_not_secrets(line):
    assert find_secrets(line) == ()
