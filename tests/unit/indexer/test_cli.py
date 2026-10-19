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
