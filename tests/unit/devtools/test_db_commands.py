import subprocess

import pytest

from qello_knowledge.devtools import db

SCHEME = "postgres" + "ql"


class FakeRunner:
    def __init__(self, failing_sql: tuple[str, ...] = (), running: bool = False, up_ok: bool = True) -> None:
        self.calls: list[list[str]] = []
        self.failing_sql = failing_sql
        self.running = running
        self.up_ok = up_ok

    def __call__(self, args, **kwargs):
        args = list(args)
        self.calls.append(args)
        code = 0
        stdout = ""
        if "ps" in args:
            stdout = "abc\n" if self.running else ""
        elif "up" in args:
            code = 0 if self.up_ok else 1
        elif "psql" in args and any(name in args[-1] for name in self.failing_sql):
            code = 1
        return subprocess.CompletedProcess(args, code, stdout, "")


@pytest.fixture
def runner(monkeypatch):
    def install(**kwargs) -> FakeRunner:
        fake = FakeRunner(**kwargs)
        monkeypatch.setattr(db, "_run", fake)
        monkeypatch.setattr(db, "_port_in_use", lambda port: False)
        return fake

    return install


def test_up_starts_compose_without_removing_volumes(runner) -> None:
    fake = runner()
    assert db.up({}) == 0
    up_calls = [c for c in fake.calls if "up" in c]
    assert up_calls == [["docker", "compose", "up", "-d", "--wait", "db"]]
    assert not any("--volumes" in c or "-v" in c[:4] for c in fake.calls)


def test_up_enables_both_extensions(runner) -> None:
    fake = runner()
    db.up({})
    sql = [c[-1] for c in fake.calls if "psql" in c]
    assert sql == ["CREATE EXTENSION IF NOT EXISTS vector", "CREATE EXTENSION IF NOT EXISTS pgroonga"]


def test_missing_extension_is_named_and_fails(runner, capsys) -> None:
    runner(failing_sql=("pgroonga",))
    assert db.up({}) == 1
    assert "pgroonga" in capsys.readouterr().err


def test_port_conflict_explains_override(runner, monkeypatch, capsys) -> None:
    fake = runner()
    monkeypatch.setattr(db, "_port_in_use", lambda port: True)
    assert db.up({"QK_LOCAL_DB_PORT": "6000"}) == 1
    err = capsys.readouterr().err
    assert "6000" in err
    assert "QK_LOCAL_DB_PORT" in err
    assert not any("up" in c for c in fake.calls)


def test_reset_refuses_remote_target(runner, capsys) -> None:
    fake = runner()
    assert db.reset({"DATABASE_URL": f"{SCHEME}://qk@db.example.com:54322/postgres"}) == 1
    assert fake.calls == []
    assert "거부" in capsys.readouterr().err


def test_reset_removes_volumes_then_starts(runner) -> None:
    fake = runner()
    assert db.reset({}) == 0
    assert fake.calls[0] == ["docker", "compose", "down", "--volumes"]
    assert any("up" in c for c in fake.calls[1:])
