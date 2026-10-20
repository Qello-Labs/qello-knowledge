import pytest

from qello_knowledge.indexer.cli import main
from tests.unit.fakes import valid_environ
from tests.unit.review_records import review_args


@pytest.fixture
def env(monkeypatch, tmp_path):
    def apply(values: dict[str, str]) -> list[str]:
        for name in valid_environ():
            monkeypatch.delenv(name, raising=False)
        for name, value in values.items():
            monkeypatch.setenv(name, value)
        return ["--env-file", str(tmp_path / ".env")]

    return apply


def test_run_with_valid_settings_reports_and_exits_zero(env, capsys, tmp_path) -> None:
    # 저장소의 config/sources.toml은 활성 자료원을 가질 수 있으므로, 활성 자료원이 없는 설정을 따로 쓴다.
    sources = tmp_path / "sources.toml"
    sources.write_text('[[source]]\nname = "old-docs"\nkind = "fake"\nenabled = false\n', encoding="utf-8")
    extra = env(valid_environ())
    assert main(["run", *extra, "--sources", str(sources)]) == 0
    out = capsys.readouterr().out
    assert "결과: 통과" in out
    assert "수집할 자료원 없음" in out


def test_run_with_missing_settings_exits_one(env, capsys) -> None:
    extra = env({})
    assert main(["run", *extra]) == 1
    assert "수집할 자료원 없음" not in capsys.readouterr().out


def test_check_only_checks(env, capsys) -> None:
    extra = env(valid_environ())
    assert main(["check", *extra]) == 0
    assert "수집할 자료원 없음" not in capsys.readouterr().out


def test_usage_error_exits_two() -> None:
    with pytest.raises(SystemExit) as excinfo:
        main(["unknown"])
    assert excinfo.value.code == 2


@pytest.mark.parametrize(("name", "code"), [("valid", 0), ("missing_fields", 1), ("unknown_kind", 1)])
def test_sources_check_never_sends_requests(name, code, capsys, monkeypatch, tmp_path):
    from qello_knowledge.adapters.replay import ReplayTransport

    def unexpected_send(self, request):
        pytest.fail("설정 점검 중 전송을 부르면 안 된다")

    monkeypatch.setattr(ReplayTransport, "send", unexpected_send)
    reviews = review_args(f"tests/fixtures/sources/{name}.toml", tmp_path / "reviews")
    assert main(["sources", "check", "--sources", f"tests/fixtures/sources/{name}.toml", *reviews]) == code
    if name == "unknown_kind":
        assert "결정 기록이 필요하다(AGENTS.md 3.1)" in capsys.readouterr().out


def test_sources_file_missing_and_bad_toml_fail(tmp_path):
    path = tmp_path / "sources.toml"
    assert main(["sources", "check", "--sources", str(path)]) == 1
    path.write_text("[[source]\n")
    assert main(["sources", "check", "--sources", str(path)]) == 1


def test_run_validates_sources_and_reports_each_source(env, capsys, tmp_path):
    extra = env(valid_environ())
    assert main(["run", *extra, "--sources", "tests/fixtures/sources/invalid.toml"]) == 1
    assert "수집할 자료원 없음" not in capsys.readouterr().out
    assert (
        main(
            [
                "run",
                *extra,
                "--sources",
                "tests/fixtures/sources/valid.toml",
                *review_args("tests/fixtures/sources/valid.toml", tmp_path / "reviews"),
            ]
        )
        == 0
    )
    out = capsys.readouterr().out
    assert "수집 대기" in out and "비활성" in out


def test_sources_check_json_and_default_empty_config(capsys, tmp_path):
    import json

    assert (
        main(
            [
                "sources",
                "check",
                "--sources",
                "tests/fixtures/sources/valid.toml",
                "--json",
                *review_args("tests/fixtures/sources/valid.toml", tmp_path / "reviews"),
            ]
        )
        == 0
    )
    output = capsys.readouterr().out
    assert len(output.splitlines()) == 1 and json.loads(output)["ok"]
    assert main(["sources", "check"]) == 0


@pytest.mark.parametrize("field", ["auth", "scope"])
def test_disabled_source_token_rejected_before_run_without_printing_value(env, capsys, tmp_path, field):
    marker = "cfat" + "_" + "synthetic" * 5
    text = '[[source]]\nname = "old-docs"\nkind = "fake"\nenabled = false\n'
    if field == "auth":
        text += f'auth = "{marker}"\n'
    else:
        text += f'[source.scope]\ninclude = ["{marker}"]\n'
    path = tmp_path / "disabled.toml"
    path.write_text(text)
    extra = env(valid_environ())
    for command in (["sources", "check"], ["run", *extra]):
        assert main([*command, "--sources", str(path)]) == 1
        output = capsys.readouterr().out
        assert "TOKEN_VALUE" in output and marker not in output
        assert "수집할 자료원 없음" not in output


# --- QK-SEC-001 security check (contracts/cli.md) ---

SEC = ["--sources", "tests/fixtures/security/sources.toml"]


def test_security_check_passes_with_version_and_counts(capsys):
    assert main(["security", "check", *SEC, "--exceptions", "tests/fixtures/security/valid_exceptions.toml"]) == 0
    out = capsys.readouterr().out
    assert "규칙 버전   sec-" in out and "비밀값 규칙 16개, 기본 제외 범주 7개, 예외 2건" in out
    assert "github_repo_files=github-visibility-v1, fake=fake-visibility-v1" in out and "결과: 통과" in out
    assert "setup.md" not in out and "자리표시" not in out


def test_security_check_reports_entry_field_and_code_only(capsys):
    assert main(["security", "check", *SEC, "--exceptions", "tests/fixtures/security/invalid_exceptions.toml"]) == 1
    out = capsys.readouterr().out
    assert "exception[5].rule  UNKNOWN_RULE" in out and "exception[6].path  WILDCARD_PATH" in out
    assert "결과: 실패 (오류 9)" in out
    assert "outside" not in out and "와일드카드" not in out and "docs/" not in out


def test_security_check_json_is_one_line(capsys):
    import json

    assert main(["security", "check", *SEC, "--exceptions", "tests/fixtures/security/absent.toml", "--json"]) == 0
    output = capsys.readouterr().out
    data = json.loads(output)
    assert len(output.splitlines()) == 1 and data["ok"] and data["exceptions"] == 0 and data["secret_rules"] == 16
    assert data["access_rules"] == {"github_repo_files": "github-visibility-v1", "fake": "fake-visibility-v1"}


def test_security_check_with_bad_sources_reports_like_sources_check(capsys):
    assert main(["security", "check", "--sources", "tests/fixtures/sources/invalid.toml"]) == 1
    assert "자료원 설정 점검" in capsys.readouterr().out


def test_run_stops_on_bad_exceptions_without_requests(env, capsys, monkeypatch, tmp_path):
    from qello_knowledge.adapters.replay import ReplayTransport

    monkeypatch.setattr(ReplayTransport, "send", lambda self, request: pytest.fail("원본 호출 금지"))
    extra = env(valid_environ())
    extra += review_args("tests/fixtures/security/sources.toml", tmp_path / "reviews")
    bad = ["--exceptions", "tests/fixtures/security/invalid_exceptions.toml"]
    assert main(["run", *extra, *SEC, *bad]) == 1
    out = capsys.readouterr().out
    assert "보안 규칙 점검" in out and "수집 대기" not in out
    assert main(["run", *extra, *SEC, "--exceptions", "tests/fixtures/security/valid_exceptions.toml"]) == 0


def test_default_security_check_passes(capsys):
    assert main(["security", "check"]) == 0


@pytest.mark.parametrize("json_output", [False, True])
def test_reviews_missing_fail_before_transport(env, capsys, monkeypatch, tmp_path, json_output):
    from qello_knowledge.adapters.http import HttpsTransport

    monkeypatch.setattr(HttpsTransport, "__init__", lambda *a, **kw: pytest.fail("전송 생성 금지"))
    extra = env(valid_environ())
    for command in (["sources", "check"], ["run", *extra]):
        args = [*command, "--sources", "tests/fixtures/sources/valid.toml", "--reviews", str(tmp_path)]
        if json_output:
            args.append("--json")
        assert main(args) == 1
        assert "REVIEW_MISSING" in capsys.readouterr().out


@pytest.mark.parametrize("enabled", [False, True])
def test_extension_failure_reaches_cli_including_disabled(env, capsys, tmp_path, enabled):
    path = tmp_path / "sources.toml"
    path.write_text(
        '[[source]]\nname = "docs"\nkind = "fake"\nenabled = '
        + str(enabled).lower()
        + '\n[source.scope]\ninclude = ["**/*.org"]\n'
    )
    for command in (["sources", "check"], ["run", *env(valid_environ())]):
        assert main([*command, "--sources", str(path), "--reviews", str(tmp_path), "--json"]) == 1
        output = capsys.readouterr().out
        assert "UNKNOWN_EXTENSION" in output and "**/*.org" not in output


def test_mismatched_review_uses_source_report(env, capsys, tmp_path):
    sources = "tests/fixtures/sources/valid.toml"
    reviews = review_args(sources, tmp_path / "reviews")
    path = tmp_path / "reviews/docs.toml"
    path.write_text(path.read_text().replace('"**/*.md"', '"other/**"'))
    for command in (["sources", "check"], ["run", *env(valid_environ())]):
        assert main([*command, "--sources", sources, *reviews]) == 1
        output = capsys.readouterr().out
        assert "REVIEW_SCOPE_MISMATCH" in output and "other/**" not in output


def test_invalid_disabled_name_does_not_crash_scope_wrapper(tmp_path, capsys):
    path = tmp_path / "sources.toml"
    path.write_text("""[[source]]
name = "valid-disabled"
kind = "fake"
enabled = false
[source.scope]
include = ["**/*.md"]
[[source]]
name = ["invalid-name-value"]
kind = "fake"
enabled = false
[source.scope]
include = ["**/*.md"]
""")
    assert main(["sources", "check", "--sources", str(path)]) == 1
    output = capsys.readouterr().out
    assert "INVALID name" in output and "invalid-name-value" not in output
