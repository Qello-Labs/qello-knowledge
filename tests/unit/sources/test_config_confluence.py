"""Confluence 자료원 범위 값 검증(QK-ING-003 data-model 1절, contracts/source-config.md). GitHub 결과는 그대로다."""

import json

import pytest

from qello_knowledge.sources.config import load_sources

BASE = {
    "include": '["**"]',
    "space_key": '"SCRUM"',
    "space_id": '"12345"',
    "judge_mode": '"site_users"',
    "doc_types": '{ "111" = "회의록", "222" = "용어집" }',
    "exclude_trees": '["333"]',
}


def _write(tmp_path, scope=None, enabled=True, drop=()):
    values = BASE | (scope or {})
    lines = [
        "[[source]]",
        'name = "confluence-scrum"',
        'kind = "confluence_pages"',
        f"enabled = {'true' if enabled else 'false'}",
        'auth = "ATLASSIAN_API_TOKEN"',
        "[source.scope]",
        *(f"{key} = {value}" for key, value in values.items() if key not in drop),
    ]
    path = tmp_path / "sources.toml"
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return load_sources(path)


def test_valid_scope_is_normalized(tmp_path):
    configs, issues = _write(tmp_path)
    assert issues == ()
    config = configs[0]
    assert config.allowed_hosts == ("api.atlassian.com",)
    assert config.scope.include == ("**",) and config.scope.exclude == ()
    extra = dict(config.scope.extra)
    assert extra["space_key"] == "SCRUM" and extra["space_id"] == "12345" and extra["judge_mode"] == "site_users"
    assert "team_group_id" not in extra
    assert extra["doc_types"] == json.dumps(
        {"111": "회의록", "222": "용어집"}, ensure_ascii=False, separators=(",", ":")
    )
    assert extra["exclude_trees"] == '["333"]'


def test_doc_types_and_trees_are_canonical(tmp_path):
    configs, _ = _write(tmp_path, {"doc_types": '{ "222" = "용어집", "111" = "회의록" }'})
    assert dict(configs[0].scope.extra)["doc_types"] == '{"111":"회의록","222":"용어집"}'


def test_team_group_mode(tmp_path):
    configs, issues = _write(tmp_path, {"judge_mode": '"team_group"', "team_group_id": '"grp-1"'})
    assert issues == ()
    assert dict(configs[0].scope.extra)["team_group_id"] == "grp-1"
    _, issues = _write(tmp_path, {"judge_mode": '"team_group"'})
    assert ("scope.team_group_id", "MISSING") in {(i.field, i.code) for i in issues}
    _, issues = _write(tmp_path, {"team_group_id": '"grp-1"'})
    assert ("scope.team_group_id", "INVALID") in {(i.field, i.code) for i in issues}


@pytest.mark.parametrize(
    ("scope", "drop", "field", "code"),
    [
        ({"include": '["docs/**"]'}, (), "scope.include", "INVALID"),
        ({}, ("include",), "scope.include", "MISSING"),
        ({"exclude": '["x/**"]'}, (), "scope.exclude", "INVALID"),
        ({"space_key": '"~personal"'}, (), "scope.space_key", "INVALID"),
        ({"space_key": '["SCRUM", "OTHER"]'}, (), "scope.space_key", "INVALID"),
        ({}, ("space_key",), "scope.space_key", "MISSING"),
        ({"space_id": '""'}, (), "scope.space_id", "MISSING"),
        ({"space_id": '"abc"'}, (), "scope.space_id", "INVALID"),
        ({"judge_mode": '"everyone"'}, (), "scope.judge_mode", "INVALID"),
        ({}, ("judge_mode",), "scope.judge_mode", "MISSING"),
        ({"doc_types": '{ "111" = "기타" }'}, (), "scope.doc_types", "INVALID"),
        ({"doc_types": '{ "abc" = "회의록" }'}, (), "scope.doc_types", "INVALID"),
        ({"exclude_trees": '["333", "333"]'}, (), "scope.exclude_trees", "INVALID"),
        ({"exclude_trees": '["x"]'}, (), "scope.exclude_trees", "INVALID"),
        ({"other": '"1"'}, (), "scope.other", "UNKNOWN_KEY"),
    ],
)
def test_invalid_scope_values(tmp_path, scope, drop, field, code):
    _, issues = _write(tmp_path, scope, drop=drop)
    assert (field, code) in {(issue.field, issue.code) for issue in issues}
    assert "SCRUM" not in str(issues) and "12345" not in str(issues)


def test_optional_tables_default_to_empty(tmp_path):
    configs, issues = _write(tmp_path, drop=("doc_types", "exclude_trees"))
    assert issues == ()
    extra = dict(configs[0].scope.extra)
    assert extra["doc_types"] == "{}" and extra["exclude_trees"] == "[]"


def test_disabled_source_scope_is_not_parsed(tmp_path):
    configs, issues = _write(tmp_path, {"space_id": '""', "include": '["docs/**"]'}, enabled=False)
    assert issues == ()
    assert configs[0].enabled is False
