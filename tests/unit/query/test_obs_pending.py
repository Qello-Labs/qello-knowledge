"""동의 전 메모리 보관의 조건·용량·수명·선점."""

from datetime import date

import pytest

from qello_knowledge.query.pending import PendingQuestions
from qello_knowledge.query.recorder import QueryRecorder
from tests.unit.query.bot_runtime import bot_runtime
from tests.unit.query.obs_builders import QUESTIONER, RATER, RUN, FakeClock, FakeQueryLog
from tests.unit.query.test_obs_query_record import run_query


def pending(**options):
    return PendingQuestions(retain_until=date(2026, 12, 31), today=lambda: date(2026, 10, 29), **options)


@pytest.mark.parametrize("change", [{"enabled": False}, {"retain_until": None}, {"retain_until": date(2026, 1, 1)}])
def test_put_gate(change):
    options = {"retain_until": date(2026, 12, 31), "today": lambda: date(2026, 10, 29), **change}
    p = PendingQuestions(**options)
    assert not p.put(RUN, QUESTIONER, "合成質問", "answered")


def test_capacity_expiry_claim_and_no_recreation():
    clock = FakeClock()
    p = pending(clock=clock.now, seconds=2, maximum=2)
    assert not p.put(RUN, None, "합성 질문", "answered")
    assert not p.put(RUN, QUESTIONER, "합성 질문", "failed")
    assert p.put(RUN, QUESTIONER, "합성 질문", "answered")
    assert not p.claim(RUN, RATER)
    original = p.claim(RUN, QUESTIONER)
    assert original.state == "waiting" and p.get(RUN).state == "claimed"
    assert not p.claim(RUN, QUESTIONER)
    p.finish(original, uncertain=True)
    assert p.get(RUN).state == "uncertain" and p.get(RUN).question == "합성 질문"
    original = p.claim(RUN, QUESTIONER)
    p.finish(original)
    assert p.get(RUN).state == "chosen" and p.get(RUN).question is None
    p.put("second", QUESTIONER, "합성 질문 2", "cannot_confirm")
    clock.advance(0.1)
    p.put("third", QUESTIONER, "합성 질문 3", "answered")
    assert p.get(RUN) is None
    original = p.claim("third", QUESTIONER)
    clock.advance(3)
    p.prune()
    p.finish(original, uncertain=True)
    assert p.get("third") is None
    p.close()
    assert len(p) == 0 and "합성 질문" not in repr(p)


def test_monitor_clears_without_requests_and_close_erases():
    clock = FakeClock()
    p = pending(clock=clock.now, seconds=0.05)
    runtime = bot_runtime(pending=p)
    p.put(RUN, QUESTIONER, "합성 질문", "answered")
    clock.advance(1)
    runtime.jobs.poll()
    assert len(p) == 0
    p.put(RUN, QUESTIONER, "합성 질문", "answered")
    runtime.jobs.close()
    assert len(p) == 0


def test_jobs_adds_only_answer_questions():
    port = FakeQueryLog()
    p = pending()
    with QueryRecorder(lambda: port, lambda: port) as recorder:
        runtime = bot_runtime(recorder=recorder, pending=p)
        run = run_query(runtime)
        assert p.get(run).question == "합성 질문 1"
        runtime.jobs.close()
        assert not len(p)


def test_real_monitor_prunes_without_accessing_pending():
    from threading import Event

    from qello_knowledge.query.jobs import QueryJobs

    clock = FakeClock()
    p = pending(clock=clock.now, seconds=1)
    jobs = QueryJobs(pipeline=lambda *args: None, deliver=lambda *args: None, pending=p)
    try:
        p.put(RUN, QUESTIONER, "합성 질문 1", "answered")
        clock.advance(2)
        Event().wait(0.15)
        # get/len은 정리도 수행하므로 내부 저장소를 직접 본다.
        assert p._items == {}
    finally:
        jobs.close()
