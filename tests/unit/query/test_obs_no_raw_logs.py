"""실패 원문·질문·답변·식별자·합성 비밀값이 출력 경계를 넘지 않는다."""

import io
import json

from qello_knowledge.indexer.cli import main
from qello_knowledge.query.recorder import QueryRecorder
from tests.unit.query.bot_runtime import bot_request
from tests.unit.query.obs_builders import QUESTIONER, RATER, RUN, FakeQueryLog, sources
from tests.unit.query.test_obs_consent_flow import click, consent_runtime
from tests.unit.synthetic_secrets import SYNTHETIC


def test_failure_paths_never_print_raw(capsys):
    secret = SYNTHETIC["cloudflare-account"]
    raw = "합성 질문 1 합성 답변 " + QUESTIONER + " " + RATER + " " + secret
    error = ValueError(raw)
    port = FakeQueryLog(feedback=error, store_question=error, question_status=error, sources=error)
    with QueryRecorder(lambda: port, lambda: port) as recorder:
        runtime, p = consent_runtime(recorder)
        click(runtime, "up")
        click(runtime, "keep")
        click(runtime, "skip")
        bot_request(runtime, sources())
        runtime.jobs.close()

    class FailedAdmin:
        def erase_user(self, *args, **kwargs):
            raise error

        def close(self):
            pass

    assert (
        main(
            ["queries", "erase-user", "--confirm", "--env-file", "/dev/null"],
            stdin=io.StringIO(QUESTIONER + "\n"),
            queries_factory=lambda source: FailedAdmin(),
        )
        == 4
    )
    out = capsys.readouterr()
    for value in ("합성 질문 1", "합성 답변", QUESTIONER, RATER, secret, RUN):
        assert value not in out.out + out.err
    lines = [json.loads(line) for line in out.err.splitlines() if line.startswith("{")]
    assert len(lines) == 4 and all(set(line) == {"kind", "action", "result", "elapsed_ms"} for line in lines)


def test_cli_argument_and_close_failures_are_safe(capsys):
    assert main(["queries", "erase-user", QUESTIONER]) == 2

    class BadClose:
        def erase_user(self, *args, **kwargs):
            return {"texts_deleted": 0}

        def close(self):
            raise ValueError("합성 질문 1 " + QUESTIONER)

    assert (
        main(
            ["queries", "erase-user", "--env-file", "/dev/null"],
            stdin=io.StringIO(QUESTIONER + "\n"),
            queries_factory=lambda source: BadClose(),
        )
        == 4
    )
    out = capsys.readouterr()
    assert QUESTIONER not in out.out + out.err and "합성 질문 1" not in out.out + out.err


def test_cli_stdin_failure_is_safe(capsys):
    class BadInput:
        def readline(self, *args):
            raise ValueError("합성 질문 1 " + QUESTIONER)

    assert main(["queries", "erase-user", "--env-file", "/dev/null"], stdin=BadInput()) == 2
    out = capsys.readouterr()
    assert QUESTIONER not in out.err and "합성 질문 1" not in out.err
