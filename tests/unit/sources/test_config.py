from pathlib import Path

import pytest

from qello_knowledge.domain.scope import in_scope
from qello_knowledge.sources.config import load_sources

ROOT = Path("tests/fixtures/sources")


@pytest.mark.parametrize(
    ("filename", "code", "field"),
    [
        ("missing_fields", "MISSING", "scope.include"),
        ("unknown_kind", "UNKNOWN_KIND", "kind"),
        ("unknown_key", "UNKNOWN_KEY", "max_retrise"),
        ("duplicate_name", "DUPLICATE_NAME", "name"),
        ("bad_auth_name", "UNKNOWN_AUTH_SETTING", "auth"),
    ],
)
def test_invalid_sources_report_field_and_code_without_value(filename, code, field):
    configs, issues = load_sources(ROOT / f"{filename}.toml")
    assert any(issue.code == code and issue.field == field for issue in issues)
    if code == "UNKNOWN_KIND":
        assert "결정 기록이 필요하다(AGENTS.md 3.1)" in str(issues[0])
    assert "notion" not in str(issues) and "UNKNOWN_SETTING" not in str(issues)


def test_defaults_and_disabled_sources(tmp_path):
    text = (ROOT / "valid.toml").read_text() + 'auth = 42\nunknown = "ignored"\n'
    path = tmp_path / "sources.toml"
    path.write_text(text)
    configs, issues = load_sources(path)
    assert not issues
    config, disabled = configs
    assert config.allowed_hosts == ("fake.invalid",)
    assert config.limits.max_requests_per_minute == 60
    assert config.limits.max_requests_per_run == 2000
    assert config.limits.max_wait_seconds == 300
    assert config.limits.max_run_seconds == 1800
    assert config.retry.max_retries == 3
    assert config.retry.initial_backoff_seconds == 1
    assert config.retry.max_backoff_seconds == 60
    assert config.max_content_bytes == 1_000_000
    assert not disabled.enabled


def test_all_issues_are_collected():
    _, issues = load_sources(ROOT / "invalid.toml")
    assert {(issue.code, issue.field) for issue in issues} >= {
        ("MISSING", "scope.include"),
        ("UNKNOWN_KEY", "max_retrise"),
    }


def test_token_values_in_auth_and_scope_are_rejected_without_leak(tmp_path):
    token = "ghp" + "_" + "synthetic" * 5
    text = (ROOT / "token_value.toml").read_text().replace("TOKEN_PLACEHOLDER", token)
    path = tmp_path / "token.toml"
    path.write_text(text.replace("exclude = []", f'exclude = ["{token}"]'))
    configs, issues = load_sources(path)
    assert {(i.code, i.field) for i in issues} >= {("TOKEN_VALUE", "auth"), ("TOKEN_VALUE", "scope.exclude[0]")}
    assert token not in repr(issues) and token not in repr(configs)


@pytest.mark.parametrize(
    ("line", "field"),
    [
        ('name = "INVALID"', "name"),
        ('name = ""', "name"),
        ("max_content_bytes = 0", "max_content_bytes"),
        ("max_content_bytes = true", "max_content_bytes"),
        ("[source.limits]\nmax_requests_per_minute = 0", "limits.max_requests_per_minute"),
        ("[source.limits]\nmax_requests_per_second = 0", "limits.max_requests_per_second"),
        ("[source.limits]\nmax_requests_per_run = 0", "limits.max_requests_per_run"),
        ("[source.limits]\nmax_wait_seconds = -1", "limits.max_wait_seconds"),
        ("[source.limits]\nmax_run_seconds = 0", "limits.max_run_seconds"),
        ("[source.retry]\nmax_retries = -1", "retry.max_retries"),
        ("[source.retry]\ninitial_backoff_seconds = 0", "retry.initial_backoff_seconds"),
        ("[source.retry]\ninitial_backoff_seconds = 3\nmax_backoff_seconds = 2", "retry.max_backoff_seconds"),
        ("include = []", "scope.include"),
    ],
)
def test_invalid_numeric_name_and_scope_fields(tmp_path, line, field):
    text = (ROOT / "overlap.toml").read_text()
    if line.startswith("name ="):
        text = text.replace('name = "docs"', line)
    elif line.startswith("include ="):
        text = text.replace('include = ["**/*.md"]', line)
    elif line.startswith("["):
        text += "\n" + line + "\n"
    else:
        text = text.replace("enabled = true", "enabled = true\n" + line)
    path = tmp_path / "bad.toml"
    path.write_text(text)
    _, issues = load_sources(path)
    assert any(i.code == "INVALID" and i.field == field for i in issues)


def test_github_scope_auth_and_default_host(tmp_path):
    text = """[[source]]
name = "repo"
kind = "github_repo_files"
enabled = true
auth = "GITHUB_API_TOKEN"
[source.scope]
repo = "example/docs"
ref = "main"
include = ["**/*.md"]
"""
    path = tmp_path / "github.toml"
    path.write_text(text)
    configs, issues = load_sources(path)
    assert not issues
    assert configs[0].allowed_hosts == ("api.github.com",)
    path.write_text(text.replace('repo = "example/docs"', 'repo = "broken"').replace('ref = "main"\n', ""))
    _, issues = load_sources(path)
    assert {(i.code, i.field) for i in issues} >= {("INVALID", "scope.repo"), ("MISSING", "scope.ref")}
    path.write_text(text.replace('auth = "GITHUB_API_TOKEN"\n', ""))
    _, issues = load_sources(path)
    assert any(i.code == "MISSING" and i.field == "auth" for i in issues)


def test_overlap_excludes_before_collection():
    configs, issues = load_sources(ROOT / "overlap.toml")
    assert not issues
    scope = configs[0].scope
    assert not in_scope("docs/a.md", scope.include, scope.exclude)


@pytest.mark.parametrize("auth", ["[]", "{}", "123", "true"])
def test_non_string_auth_reports_issue_instead_of_crashing(tmp_path, auth):
    text = (ROOT / "overlap.toml").read_text().replace("enabled = true", f"enabled = true\nauth = {auth}")
    path = tmp_path / "bad-auth.toml"
    path.write_text(text)
    _, issues = load_sources(path)
    assert any(i.field == "auth" and i.code == "UNKNOWN_AUTH_SETTING" for i in issues)


def test_long_path_pattern_is_not_a_token(tmp_path):
    pattern = "specs/QK-ING-001-source-adapter-contract/**/*.md"
    text = (ROOT / "overlap.toml").read_text().replace("**/*.md", pattern)
    path = tmp_path / "long-pattern.toml"
    path.write_text(text)
    configs, issues = load_sources(path)
    assert len(pattern) > 40 and not issues
    assert configs[0].scope.include == (pattern,)


@pytest.mark.parametrize("prefix", ["ghp", "github_pat", "cfat", "postgres", "postgresql"])
def test_known_token_prefix_and_postgres_scheme_report_only_token_value(tmp_path, prefix):
    marker = prefix + ("://" + "example.invalid/docs" if prefix.startswith("postgres") else "_" + "synthetic" * 5)
    text = (ROOT / "token_value.toml").read_text().replace("TOKEN_PLACEHOLDER", marker)
    path = tmp_path / "token-prefix.toml"
    path.write_text(text)
    configs, issues = load_sources(path)
    assert [(i.field, i.code) for i in issues] == [("auth", "TOKEN_VALUE")]
    assert marker not in repr(configs) + repr(issues)


@pytest.mark.parametrize("field", ["name", "kind", "enabled", "scope", "scope.include", "scope.include[0]"])
def test_token_fields_do_not_produce_cascading_format_errors(tmp_path, field):
    marker = "ghp" + "_" + "synthetic" * 5
    text = (ROOT / "overlap.toml").read_text()
    old, new = {
        "name": ('name = "docs"', f'name = "{marker}"'),
        "kind": ('kind = "fake"', f'kind = "{marker}"'),
        "enabled": ("enabled = true", f'enabled = "{marker}"'),
        "scope": ('[source.scope]\ninclude = ["**/*.md"]\nexclude = ["docs/**"]', f'scope = "{marker}"'),
        "scope.include": ('include = ["**/*.md"]', f'include = "{marker}"'),
        "scope.include[0]": ('include = ["**/*.md"]', f'include = ["{marker}"]'),
    }[field]
    path = tmp_path / "one-error.toml"
    path.write_text(text.replace(old, new))
    configs, issues = load_sources(path)
    assert [(i.field, i.code) for i in issues] == [(field, "TOKEN_VALUE")]
    assert marker not in repr(configs) + repr(issues)


@pytest.mark.parametrize("field", ["auth", "scope.include[0]"])
def test_disabled_source_still_rejects_token_values(tmp_path, field):
    marker = "cfat" + "_" + "synthetic" * 5
    text = (ROOT / "overlap.toml").read_text().replace("enabled = true", "enabled = false")
    if field == "auth":
        text = text.replace("enabled = false", f'enabled = false\nauth = "{marker}"')
    else:
        text = text.replace('include = ["**/*.md"]', f'include = ["{marker}"]')
    path = tmp_path / "disabled-token.toml"
    path.write_text(text)
    configs, issues = load_sources(path)
    assert not configs[0].enabled
    assert [(i.field, i.code) for i in issues] == [(field, "TOKEN_VALUE")]
    assert marker not in repr(configs) + repr(issues)


def test_token_error_does_not_hide_an_independent_invalid_pattern(tmp_path):
    marker = "ghp" + "_" + "synthetic" * 5
    text = (ROOT / "overlap.toml").read_text().replace('include = ["**/*.md"]', f'include = ["{marker}", 123]')
    path = tmp_path / "two-errors.toml"
    path.write_text(text)
    _, issues = load_sources(path)
    assert {(i.field, i.code) for i in issues} == {("scope.include[0]", "TOKEN_VALUE"), ("scope.include", "INVALID")}


@pytest.mark.parametrize(("dialect", "driver"), [("postgresql", "asyncpg"), ("postgres", "psycopg2")])
def test_postgres_driver_url_is_a_token_value(tmp_path, dialect, driver):
    marker = dialect + "+" + driver + "://" + "example.invalid/docs"
    text = (ROOT / "token_value.toml").read_text().replace("TOKEN_PLACEHOLDER", marker)
    path = tmp_path / "driver-url.toml"
    path.write_text(text)
    configs, issues = load_sources(path)
    assert [(issue.field, issue.code) for issue in issues] == [("auth", "TOKEN_VALUE")]
    assert marker not in repr(configs) + repr(issues)


def test_allowed_hosts_are_normalized_to_lowercase(tmp_path):
    text = (ROOT / "overlap.toml").read_text()
    text = text.replace("enabled = true", 'enabled = true\nallowed_hosts = ["FAKE.invalid"]')
    path = tmp_path / "mixed-case-host.toml"
    path.write_text(text)
    configs, issues = load_sources(path)
    assert not issues
    assert configs[0].allowed_hosts == ("fake.invalid",)


@pytest.mark.parametrize("location", ["leading_space", "path_segment", "url_segment"])
def test_token_prefix_detection_remains_anchored_at_start(tmp_path, location):
    marker = "sk" + "-" + "synthetic" * 5
    value = {
        "leading_space": " " + marker,
        "path_segment": "docs/" + marker + "/**",
        "url_segment": "https://example.invalid/docs/" + marker,
    }[location]
    text = (ROOT / "overlap.toml").read_text().replace("**/*.md", value)
    path = tmp_path / "embedded-prefix.toml"
    path.write_text(text)
    configs, issues = load_sources(path)
    assert not issues
    assert configs[0].scope.include == (value,)


@pytest.mark.parametrize(
    ("top", "scope", "field"),
    [
        ("include_secrets = true\n", "", "include_secrets"),
        ("", "disable_default_exclusions = true\n", "scope.disable_default_exclusions"),
    ],
)
def test_default_exclusions_cannot_be_disabled_by_config(tmp_path, top, scope, field):
    # QK-SEC-001 FR-007: 기본 제외를 끄는 키는 없고, 그런 키는 실행 전에 실패한다.
    text = f'[[source]]\nname = "docs"\nkind = "fake"\nenabled = true\n{top}[source.scope]\ninclude = ["**"]\n{scope}'
    path = tmp_path / "sources.toml"
    path.write_text(text)
    _, issues = load_sources(path)
    assert any(issue.code == "UNKNOWN_KEY" and issue.field == field for issue in issues)
