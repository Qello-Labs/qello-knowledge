from pathlib import Path

from qello_knowledge.config.loader import SecretValue, SettingStatus, load, parse_env_file
from qello_knowledge.config.registry import Entrypoint
from tests.unit.fakes import valid_environ


def _status(settings, name: str) -> SettingStatus:
    return next(item.status for item in settings.items if item.spec.name == name)


def test_parse_env_file_handles_comments_quotes_and_export() -> None:
    text = "# 주석\n\nA=1\nexport B = '두 단어'\nC=\"x\"\nbroken\n"
    assert parse_env_file(text) == {"A": "1", "B": "두 단어", "C": "x"}


def test_environment_overrides_env_file(tmp_path: Path) -> None:
    env_file = tmp_path / ".env"
    env_file.write_text("QK_LOG_LEVEL=DEBUG\n", encoding="utf-8")
    settings = load(Entrypoint.INDEX, environ={"QK_LOG_LEVEL": "ERROR"}, env_file=env_file)
    assert settings.get("QK_LOG_LEVEL") == "ERROR"


def test_env_file_is_used_when_environment_lacks_name(tmp_path: Path) -> None:
    env_file = tmp_path / ".env"
    env_file.write_text("QK_LOG_LEVEL=DEBUG\n", encoding="utf-8")
    assert load(Entrypoint.INDEX, environ={}, env_file=env_file).get("QK_LOG_LEVEL") == "DEBUG"


def test_missing_env_file_is_not_an_error(tmp_path: Path) -> None:
    settings = load(Entrypoint.INDEX, environ={}, env_file=tmp_path / "없음.env")
    assert _status(settings, "DATABASE_URL") is SettingStatus.MISSING


def test_blank_values_are_missing() -> None:
    settings = load(Entrypoint.INDEX, environ={"DATABASE_URL": "", "GITHUB_API_TOKEN": "   "}, env_file=None)
    assert _status(settings, "DATABASE_URL") is SettingStatus.MISSING
    assert _status(settings, "GITHUB_API_TOKEN") is SettingStatus.MISSING


def test_default_is_used_for_non_secret() -> None:
    assert load(Entrypoint.QUERY, environ={}, env_file=None).get("QK_LOG_LEVEL") == "INFO"


def test_secret_values_are_masked() -> None:
    settings = load(Entrypoint.INDEX, environ=valid_environ(), env_file=None)
    token = settings.get("GITHUB_API_TOKEN")
    assert isinstance(token, SecretValue)
    assert str(token) == "***"
    assert "***" in repr(token)
    assert token.reveal() == valid_environ()["GITHUB_API_TOKEN"]
