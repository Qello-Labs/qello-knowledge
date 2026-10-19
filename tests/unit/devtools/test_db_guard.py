import pytest

from qello_knowledge.devtools.db import is_local_target, local_port

SCHEME = "postgres" + "ql"


def _url(host: str, port: int) -> str:
    return f"{SCHEME}://qk@{host}:{port}/postgres"


def test_missing_url_means_compose_default() -> None:
    assert is_local_target({})


@pytest.mark.parametrize("host", ["localhost", "127.0.0.1", "[::1]"])
def test_loopback_with_local_port_is_local(host: str) -> None:
    assert is_local_target({"DATABASE_URL": _url(host, 54322)})


def test_custom_local_port_is_respected() -> None:
    assert is_local_target({"DATABASE_URL": _url("127.0.0.1", 6000), "QK_LOCAL_DB_PORT": "6000"})
    assert local_port({"QK_LOCAL_DB_PORT": "6000"}) == 6000


@pytest.mark.parametrize(
    "url",
    [
        _url("db.example.com", 54322),
        _url("10.0.0.5", 54322),
        _url("127.0.0.1", 5432),
        "not a url",
    ],
)
def test_other_targets_are_refused(url: str) -> None:
    assert not is_local_target({"DATABASE_URL": url})
