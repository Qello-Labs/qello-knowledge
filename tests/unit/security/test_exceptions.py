from pathlib import Path

from qello_knowledge.domain.source_config import SourceConfig
from qello_knowledge.security.exceptions import PolicyIssue, SecretException, load_exceptions
from qello_knowledge.security.policy import load_policy

FIXTURES = Path("tests/fixtures/security")
CONFIGS = (SourceConfig("docs", "fake", True), SourceConfig("old-wiki", "fake", False))


def test_valid_file_normalizes_paths_and_accepts_disabled_sources():
    exceptions, issues = load_exceptions(FIXTURES / "valid_exceptions.toml", CONFIGS)
    assert issues == ()
    assert {(e.source, e.path, e.rule) for e in exceptions} == {
        ("docs", "docs/setup.md", "assigned-secret"),
        ("old-wiki", "Docs/Setup.md", "assigned-secret"),
    }


def test_every_problem_is_reported_by_entry_field_and_code_without_values():
    _, issues = load_exceptions(FIXTURES / "invalid_exceptions.toml", CONFIGS)
    assert set(issues) == {
        PolicyIssue(None, "extra", "UNKNOWN_KEY"),
        PolicyIssue(1, "note", "UNKNOWN_KEY"),
        PolicyIssue(2, "path", "MISSING"),
        PolicyIssue(3, "path", "INVALID"),
        PolicyIssue(4, "source", "UNKNOWN_SOURCE"),
        PolicyIssue(5, "rule", "UNKNOWN_RULE"),
        PolicyIssue(6, "path", "WILDCARD_PATH"),
        PolicyIssue(7, "path", "INVALID_PATH"),
        PolicyIssue(8, "path", "DUPLICATE"),
    }
    rendered = "\n".join(str(issue) for issue in issues)
    assert "outside" not in rendered and "와일드카드" not in rendered and "docs/" not in rendered


def test_broken_toml_is_invalid_file():
    _, issues = load_exceptions(FIXTURES / "broken_exceptions.toml", CONFIGS)
    assert issues == (PolicyIssue(None, "file", "INVALID_FILE"),)


def test_missing_file_means_no_exceptions(tmp_path):
    assert load_exceptions(tmp_path / "absent.toml", CONFIGS) == (frozenset(), ())


def test_load_policy_refuses_on_any_issue_and_versions_exceptions():
    policy, issues = load_policy(FIXTURES / "invalid_exceptions.toml", CONFIGS)
    assert policy is None and issues
    policy, issues = load_policy(FIXTURES / "valid_exceptions.toml", CONFIGS)
    empty, _ = load_policy(FIXTURES / "absent.toml", CONFIGS)
    assert issues == () and policy.version != empty.version
    assert SecretException("docs", "docs/setup.md", "assigned-secret", "x").rule in policy.exempt_rules(
        "docs", "docs/setup.md"
    )
