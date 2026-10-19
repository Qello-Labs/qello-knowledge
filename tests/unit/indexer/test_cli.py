import pytest

from qello_knowledge.indexer.cli import main
from tests.unit.fakes import valid_environ


@pytest.fixture
def env(monkeypatch, tmp_path):
    def apply(values: dict[str, str]) -> list[str]:
        for name in valid_environ():
            monkeypatch.delenv(name, raising=False)
        for name, value in values.items():
            monkeypatch.setenv(name, value)
        return ["--env-file", str(tmp_path / ".env")]

    return apply


def test_run_with_valid_settings_reports_and_exits_zero(env, capsys) -> None:
    extra = env(valid_environ())
    assert main(["run", *extra]) == 0
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
def test_sources_check_never_sends_requests(name, code, capsys, monkeypatch):
    from qello_knowledge.adapters.replay import ReplayTransport

    def unexpected_send(self, request):
        pytest.fail("설정 점검 중 전송을 부르면 안 된다")

    monkeypatch.setattr(ReplayTransport, "send", unexpected_send)
    assert main(["sources", "check", "--sources", f"tests/fixtures/sources/{name}.toml"]) == code
    if name == "unknown_kind":
        assert "결정 기록이 필요하다(AGENTS.md 3.1)" in capsys.readouterr().out


def test_sources_file_missing_and_bad_toml_fail(tmp_path):
    path = tmp_path / "sources.toml"
    assert main(["sources", "check", "--sources", str(path)]) == 1
    path.write_text("[[source]\n")
    assert main(["sources", "check", "--sources", str(path)]) == 1


def test_run_validates_sources_and_reports_each_source(env, capsys):
    extra = env(valid_environ())
    assert main(["run", *extra, "--sources", "tests/fixtures/sources/invalid.toml"]) == 1
    assert "수집할 자료원 없음" not in capsys.readouterr().out
    assert main(["run", *extra, "--sources", "tests/fixtures/sources/valid.toml"]) == 0
    out = capsys.readouterr().out
    assert "수집 대기" in out and "비활성" in out


def test_sources_check_json_and_default_empty_config(capsys):
    import json

    assert main(["sources", "check", "--sources", "tests/fixtures/sources/valid.toml", "--json"]) == 0
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
