"""내보내기는 저장소 밖 새 파일·0600, 동의 질문만 식별자 없이."""

import json
import stat
from pathlib import Path

import pytest

from qello_knowledge.adapters.postgres.query_log_admin import PostgresQueryLogAdmin
from qello_knowledge.indexer.cli import main
from tests.localdb.query.obs_db import obs_connection, seed_feedback, seed_record, seed_text
from tests.unit.query.obs_builders import QUESTIONER

pytestmark = pytest.mark.localdb


def test_export_down_only_all_and_existing_file(db_url, tmp_path, capsys):
    with obs_connection(db_url) as conn:
        seed_record(conn)
        seed_text(conn)
        seed_feedback(conn)
        other = "q-20261029T010204-1234abcd"
        seed_record(conn, run_id=other)
        seed_text(conn, run_id=other, question="합성 질문 2")

        def factory(source):
            return PostgresQueryLogAdmin(db_url)

        for all_rows, count in [(False, 1), (True, 2)]:
            path = tmp_path / ("all.jsonl" if all_rows else "down.jsonl")
            args = ["queries", "export", "--out", str(path), "--env-file", "/dev/null"] + (
                ["--all"] if all_rows else []
            )
            assert main(args, queries_factory=factory) == 0
            assert stat.S_IMODE(path.stat().st_mode) == 0o600
            rows = [json.loads(line) for line in path.read_text().splitlines()]
            assert len(rows) == count
            assert set(rows[0]) == {
                "run_id",
                "received_date",
                "question",
                "context_chunk_ids",
                "context_block_sizes",
                "cited_blocks",
                "index_version",
                "feedback",
            }
            assert QUESTIONER not in path.read_text() and rows[0]["feedback"] == {"up": 0, "down": 1}
            original = path.read_bytes()
            assert main(args, queries_factory=factory) == 2 and path.read_bytes() == original
        output = capsys.readouterr()
        assert "저장소에 커밋하지 마세요" in output.out and "이 파일도 지우세요" in output.out
        assert "합성 질문" not in output.out + output.err and QUESTIONER not in output.out + output.err


def test_reject_export_inside_worktree(db_url):
    assert (
        main(
            ["queries", "export", "--out", str(Path.cwd() / "obs-export.jsonl"), "--env-file", "/dev/null"],
            queries_factory=lambda source: PostgresQueryLogAdmin(db_url),
        )
        == 2
    )
    assert not (Path.cwd() / "obs-export.jsonl").exists()
