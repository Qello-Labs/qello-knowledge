import json

from qello_knowledge.config.check import build_report
from qello_knowledge.config.loader import load
from qello_knowledge.config.registry import Entrypoint
from qello_knowledge.query.app import handle
from tests.unit.fakes import valid_environ


def _report(environ):
    return lambda: build_report(load(Entrypoint.QUERY, environ=environ, env_file=None))


def test_healthz_ok_when_settings_pass() -> None:
    status, body = handle("GET", "/healthz", _report(valid_environ()))
    assert status == 200
    payload = json.loads(body)
    assert payload["entrypoint"] == "query"
    assert payload["ok"] is True


def test_healthz_503_when_settings_fail() -> None:
    status, body = handle("GET", "/healthz", _report({}))
    assert status == 503
    assert json.loads(body)["ok"] is False


def test_unknown_path_is_404() -> None:
    assert handle("GET", "/", _report({}))[0] == 404


def test_other_method_is_405() -> None:
    assert handle("POST", "/healthz", _report({}))[0] == 405
