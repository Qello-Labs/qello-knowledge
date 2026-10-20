from dataclasses import replace
from pathlib import Path

import pytest

from qello_knowledge.domain.source_config import SourceConfig, SourceScope
from qello_knowledge.sources.scope_review import ScopeReview, check_scope, extension_issues, load_review


@pytest.fixture
def config():
    return SourceConfig(
        "docs",
        "github_repo_files",
        True,
        scope=SourceScope(
            ("docs/**/*.md", "README.md"), ("docs/private/**",), (("repo", "octo/docs"), ("ref", "main"))
        ),
    )


@pytest.fixture
def record(tmp_path):
    path = tmp_path / "docs.toml"
    path.write_text(Path("tests/fixtures/source_reviews/valid.toml").read_text())
    return path


@pytest.mark.parametrize(
    "pattern,bad",
    [
        ("**/*.org", True),
        ("docs/*.m?", True),
        ("docs/*.[mM]d", True),
        ("**/*.adoc", False),
        ("**/*.MD", False),
        ("docs/**", False),
        ("README*", False),
        ("README.md", False),
    ],
)
@pytest.mark.parametrize("enabled", [True, False])
def test_extension_check_includes_disabled(pattern, bad, enabled, config):
    config = replace(config, enabled=enabled, scope=replace(config.scope, include=(pattern,)))
    issues = extension_issues(config)
    assert [(issue.field, issue.code) for issue in issues] == (
        [("scope.include[0]", "UNKNOWN_EXTENSION")] if bad else []
    )
    assert all(pattern not in str(issue) for issue in issues)


def test_missing_review_and_disabled_source(config, tmp_path):
    assert [(i.field, i.code) for i in check_scope((config,), tmp_path)] == [("review", "REVIEW_MISSING")]
    assert check_scope((replace(config, enabled=False),), tmp_path) == ()


@pytest.mark.parametrize("fixture", ["valid", "excluded"])
def test_valid_review_object_and_matching_scope(config, record, fixture):
    record.write_text(Path(f"tests/fixtures/source_reviews/{fixture}.toml").read_text())
    assert isinstance(load_review(record), ScopeReview)
    assert check_scope((config,), record.parent) == ()


@pytest.mark.parametrize("field", ["source", "reviewed_on", "reviewer_role", "method", "result", "scope"])
def test_every_required_field_missing_is_invalid(field, config, record):
    text = record.read_text()
    if field == "scope":
        text = text.split("[scope]")[0]
    else:
        text = "\n".join(line for line in text.splitlines() if not line.startswith(field + " ="))
    record.write_text(text)
    issues = check_scope((config,), record.parent)
    assert issues and all(issue.code == "REVIEW_INVALID" for issue in issues)


@pytest.mark.parametrize(
    "change",
    [
        "toml",
        "unknown",
        "source",
        "result",
        "moved_missing",
        "date_string",
        "empty_role",
        "empty_method",
        "scope_type",
        "patterns_type",
        "nested_unknown",
        "moved_type",
        "moved_unknown",
        "moved_reason",
    ],
)
def test_invalid_records_do_not_print_values(change, config, record):
    text = record.read_text()
    edits = {
        "toml": lambda s: s + "[broken",
        "unknown": lambda s: 'sensitive_key = "hidden-value"\n' + s,
        "source": lambda s: s.replace('source = "docs"', 'source = "hidden-value"'),
        "result": lambda s: s.replace('result = "개인 정보 없음"', 'result = "hidden-value"'),
        "moved_missing": lambda s: s.replace("개인 정보 없음", "개인 정보 경로 제외함"),
        "date_string": lambda s: s.replace("2026-10-20", '"hidden-value"'),
        "empty_role": lambda s: s.replace("시험용 역할", ""),
        "empty_method": lambda s: s.replace("합성 문서 전체 확인", ""),
        "scope_type": lambda s: s.split("[scope]")[0] + 'scope = "hidden-value"',
        "patterns_type": lambda s: s.replace('["docs/**/*.md", "README.md"]', '"hidden-value"'),
        "nested_unknown": lambda s: s + '\nhidden_key = "hidden-value"',
        "moved_type": lambda s: 'moved_to_exclude = "hidden-value"\n' + s,
        "moved_unknown": lambda s: (
            s + '\n[[moved_to_exclude]]\npattern = "docs/private/**"\nreason = "合成"\nhidden_key = "hidden-value"'
        ),
        "moved_reason": lambda s: s + '\n[[moved_to_exclude]]\npattern = "docs/private/**"\nreason = ""',
    }
    record.write_text(edits[change](text))
    issues = check_scope((config,), record.parent)
    assert issues and all(issue.code == "REVIEW_INVALID" for issue in issues)
    assert "hidden-value" not in str(issues) and "sensitive_key" not in str(issues)


@pytest.mark.parametrize("change", ["repo", "ref", "include", "exclude", "order", "moved"])
def test_scope_mismatch_including_order(config, record, change):
    text = record.read_text()
    if change == "order":
        text = text.replace('["docs/**/*.md", "README.md"]', '["README.md", "docs/**/*.md"]')
    elif change == "moved":
        text += '\n[[moved_to_exclude]]\npattern = "hidden-value"\nreason = "합성"'
    else:
        text = text.replace(
            {
                "repo": '"octo/docs"',
                "ref": '"main"',
                "include": '["docs/**/*.md", "README.md"]',
                "exclude": '["docs/private/**"]',
            }[change],
            '["hidden-value"]' if change in {"include", "exclude"} else '"hidden-value"',
        )
    record.write_text(text)
    issues = check_scope((config,), record.parent)
    assert issues and all(issue.code == "REVIEW_SCOPE_MISMATCH" for issue in issues)
    assert "hidden-value" not in str(issues)


def test_fake_scope_needs_no_repo_or_ref(config, tmp_path):
    from tests.unit.review_records import write_review

    config = replace(config, kind="fake", scope=replace(config.scope, extra=()))
    write_review(config, tmp_path)
    assert check_scope((config,), tmp_path) == ()
