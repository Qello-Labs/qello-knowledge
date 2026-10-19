"""비밀 값이 점검 출력, 예외, 로그 어디에도 나오지 않는지 본다(FR-008, SC-003)."""

import logging

import pytest

from qello_knowledge.config.cli import run_check
from qello_knowledge.config.loader import load
from qello_knowledge.config.registry import Entrypoint
from qello_knowledge.indexer import cli as indexer_cli
from tests.unit.fakes import GITHUB_PREFIX, valid_environ

MARKER = "LEAKMARKER7f3a"


def _environ_with_marker(valid: bool) -> dict[str, str]:
    environ = valid_environ()
    environ["GITHUB_API_TOKEN"] = (GITHUB_PREFIX + MARKER + "x" * 20) if valid else ("bad " + MARKER)
    environ["CLOUDFLARE_API_TOKEN"] = MARKER + "c" * 40
    environ["DATABASE_URL"] = "not-a-url-" + MARKER
    return environ


@pytest.mark.parametrize("valid", [True, False])
@pytest.mark.parametrize("as_json", [True, False])
def test_check_output_never_contains_secret(valid, as_json, capsys, caplog, monkeypatch) -> None:
    caplog.set_level(logging.DEBUG)
    for name, value in _environ_with_marker(valid).items():
        monkeypatch.setenv(name, value)
    argv = ["check", "--env-file", "없는-파일.env"] + (["--json"] if as_json else [])
    indexer_cli.main(argv)
    captured = capsys.readouterr()
    for part in (MARKER, MARKER[:6]):
        assert part not in captured.out
        assert part not in captured.err
        assert part not in caplog.text


def test_settings_repr_never_contains_secret() -> None:
    settings = load(Entrypoint.INDEX, environ=_environ_with_marker(True), env_file=None)
    assert MARKER not in repr(settings)
    assert MARKER not in str(settings.get("GITHUB_API_TOKEN"))


def test_exception_message_never_contains_secret() -> None:
    settings = load(Entrypoint.INDEX, environ=_environ_with_marker(True), env_file=None)
    try:
        raise RuntimeError(f"작업 실패: {settings.get('CLOUDFLARE_API_TOKEN')}")
    except RuntimeError as error:
        assert MARKER not in str(error)


def test_run_check_returns_failure_code(capsys) -> None:
    class Args:
        json = False
        env_file = None

    code, report = run_check(Entrypoint.INDEX, Args(), environ={})
    assert code == 1
    assert not report.ok
