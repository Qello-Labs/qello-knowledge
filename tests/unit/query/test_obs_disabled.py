"""기본 꺼짐에서는 기존 본문·운영 키·질의 결과가 같다."""

import json

from qello_knowledge.query.pending import PendingQuestions
from qello_knowledge.query.recorder import QueryRecorder
from tests.unit.query.bot_runtime import bot_runtime
from tests.unit.query.obs_builders import FakeQueryLog
from tests.unit.query.test_obs_query_record import run_query


def test_disabled_preserves_response_body_and_log_values():
    port = FakeQueryLog()
    baseline = bot_runtime()
    old = []
    baseline.jobs._on_finished = old.append
    run_query(baseline)
    with QueryRecorder(lambda: port) as recorder:
        pending = PendingQuestions(enabled=False)
        runtime = bot_runtime(recorder=recorder, pending=pending)
        logs = []
        runtime.jobs._on_finished = logs.append
        run_query(runtime)
        assert [request.body for request in baseline.fake.requests] == [
            request.body for request in runtime.fake.requests
        ]
        left, right = json.loads(old[0].to_json()), json.loads(logs[0].to_json())
        left.pop("run_id")
        right.pop("run_id")
        assert left == right and right["record"] == "off"
        assert not port.calls and not len(pending) and recorder._back is None
        runtime.jobs.close()
    baseline.jobs.close()


def test_jobs_close_joins_record_threads():
    port = FakeQueryLog()
    recorder = QueryRecorder(lambda: port, lambda: port)
    runtime = bot_runtime(recorder=recorder)
    run_query(runtime)
    runtime.jobs.close()
    assert recorder._back.executor._shutdown and recorder._front.executor._shutdown
    assert port.closed
