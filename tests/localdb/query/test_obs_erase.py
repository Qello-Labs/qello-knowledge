"""관리 명령의 확인·멱등·비노출·한 트랜잭션 지우기."""

import io

import pytest

from qello_knowledge.adapters.postgres.query_log_admin import PostgresQueryLogAdmin
from qello_knowledge.indexer.cli import main
from tests.localdb.query.obs_db import obs_connection, seed_feedback, seed_record, seed_text
from tests.unit.query.obs_builders import QUESTIONER, RATER, RUN

pytestmark = pytest.mark.localdb
OTHER = "q-20261029T010204-1234abcd"


def invoke(db_url, *args, user=QUESTIONER):
    return main(
        ["queries", *args, "--env-file", "/dev/null"],
        stdin=io.StringIO(user + "\n"),
        queries_factory=lambda source: PostgresQueryLogAdmin(db_url),
    )


def test_erase_user_confirm_and_repeat(db_url, capsys):
    with obs_connection(db_url) as conn:
        seed_record(conn)
        seed_text(conn)
        seed_feedback(conn)
        seed_record(conn, run_id=OTHER, questioner_id=RATER)
        seed_text(conn, run_id=OTHER, user=RATER, question="합성 질문 2")
        seed_feedback(conn, run_id=OTHER, rater_id=QUESTIONER)
        assert invoke(db_url, "erase-user") == 0
        assert conn.execute("SELECT count(*) FROM qk.query_text").fetchone()[0] == 2
        assert invoke(db_url, "erase-user", "--confirm") == 0
        assert conn.execute("SELECT run_id FROM qk.query_text").fetchall() == [(OTHER,)]
        assert conn.execute("SELECT questioner_id FROM qk.query_record WHERE run_id=%s", (RUN,)).fetchone() == (None,)
        assert conn.execute("SELECT count(*) FROM qk.query_feedback WHERE rater_id IS NULL").fetchone()[0] == 2
        assert invoke(db_url, "erase-user", "--confirm") == 0
        out = capsys.readouterr()
        assert QUESTIONER not in out.out + out.err and "합성 질문" not in out.out + out.err
        assert "1시간" in out.out and '"texts_deleted":0' in out.out
        columns = [
            r[0]
            for r in conn.execute(
                "SELECT column_name FROM information_schema.columns "
                "WHERE table_schema='qk' AND table_name='query_erasure_run'"
            )
        ]
        assert not set(columns) & {"questioner_id", "rater_id", "user_id"}


@pytest.mark.parametrize("user", ["bad", "1" * 16, "1" * 21, "100000000000000001 extra"])
def test_invalid_stdin_does_not_echo(db_url, user, capsys):
    assert invoke(db_url, "erase-user", "--confirm", user=user) == 2
    captured = capsys.readouterr()
    assert user not in captured.out + captured.err


def test_all_texts_preserves_metadata_and_feedback(db_url, capsys):
    with obs_connection(db_url) as conn:
        seed_record(conn)
        seed_text(conn)
        seed_feedback(conn)
        assert invoke(db_url, "erase-texts") == 0
        assert conn.execute("SELECT count(*) FROM qk.query_text").fetchone()[0] == 1
        assert invoke(db_url, "erase-texts", "--confirm") == 0
        assert invoke(db_url, "erase-texts", "--confirm") == 0
        assert conn.execute("SELECT count(*) FROM qk.query_text").fetchone()[0] == 0
        assert conn.execute("SELECT count(*) FROM qk.query_record").fetchone()[0] == 1
        assert conn.execute("SELECT count(*) FROM qk.query_feedback").fetchone()[0] == 1
        assert conn.execute("SELECT kind,texts_deleted FROM qk.query_erasure_run ORDER BY id").fetchall() == [
            ("all_texts", 1),
            ("all_texts", 0),
        ]
        assert "내보낸 파일" in capsys.readouterr().out
