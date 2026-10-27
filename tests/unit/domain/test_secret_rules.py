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


# --- 한글 인접과 ASCII 경계 (#67) ---
# Python 정규식의 `\b`는 한글을 단어 문자로 본다. 경계는 ASCII 영숫자·밑줄만 기준으로 한다.

ALL_SAMPLES = {
    **BASE_SAMPLES,
    "github-fine-grained-token": SYNTHETIC["github-fine-grained"],
    "cloudflare-account-token": SYNTHETIC["cloudflare-account"],
    "discord-bot-token": SYNTHETIC["discord-bot"],
    "clickup-token": SYNTHETIC["clickup"],
}
# 줄 맨 앞에서만 보는 규칙이라 앞에 글자가 붙는 꼴은 해당하지 않는다.
LINE_START_RULES = {"env-assigned-secret"}
# 앞에 ASCII 영숫자·밑줄이 붙으면 지금처럼 잡지 않아야 하는 규칙(오탐 방지).
PREFIX_BOUNDED = (
    "aws-access-key",
    "github-token",
    "slack-token",
    "anthropic-key",
    "openai-key",
    "notion-token",
    "figma-token",
    "atlassian-token",
    "github-fine-grained-token",
    "cloudflare-account-token",
    "discord-bot-token",
    "clickup-token",
    "db-url-with-password",
)
# 뒤에 ASCII 단어 문자가 붙으면 지금처럼 잡지 않아야 하는 꼴.
SUFFIX_BOUNDED = (("aws-access-key", "B"), ("notion-token", "_"), ("slack-token", "_"))


def test_adjacency_samples_cover_every_rule():
    assert set(ALL_SAMPLES) == {rule.name for rule in RULES}


def rules_hit(line):
    return {hit.rule for hit in find_secrets(line)}


@pytest.mark.parametrize("name", sorted(set(ALL_SAMPLES) - LINE_START_RULES))
@pytest.mark.parametrize("before", ["토큰", "값은"])
def test_rule_catches_value_right_after_hangul(name, before):
    assert name in rules_hit(before + ALL_SAMPLES[name])


@pytest.mark.parametrize("name", sorted(ALL_SAMPLES))
@pytest.mark.parametrize("after", ["입니다", "을"])
def test_rule_catches_value_right_before_hangul(name, after):
    assert name in rules_hit(ALL_SAMPLES[name] + after)


@pytest.mark.parametrize("name", sorted(set(ALL_SAMPLES) - LINE_START_RULES))
def test_rule_catches_value_wrapped_in_hangul(name):
    assert name in rules_hit("토큰" + ALL_SAMPLES[name] + "입니다")


@pytest.mark.parametrize("name", sorted(set(ALL_SAMPLES) - LINE_START_RULES))
def test_rule_catches_value_between_spaces(name):
    assert name in rules_hit("토큰 " + ALL_SAMPLES[name] + " 입니다")


@pytest.mark.parametrize("name", PREFIX_BOUNDED)
@pytest.mark.parametrize("before", ["x", "Z", "7", "_"])
def test_ascii_word_prefix_still_blocks_rule(name, before):
    assert name not in rules_hit(before + ALL_SAMPLES[name])


@pytest.mark.parametrize(("name", "after"), SUFFIX_BOUNDED)
def test_ascii_word_suffix_still_blocks_rule(name, after):
    assert name not in rules_hit(ALL_SAMPLES[name] + after)
