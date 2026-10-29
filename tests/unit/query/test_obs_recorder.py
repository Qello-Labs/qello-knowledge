"""두 길 분리와 절대 마감, 실패 비노출."""

from threading import Event
from time import monotonic

from qello_knowledge.query.recorder import QueryRecorder
from tests.unit.query.obs_builders import FakeClock, FakeQueryLog


def test_lanes_do_not_wait_and_background_timeout():
    release = Event()
    front, back = FakeQueryLog(feedback="stored"), FakeQueryLog(insert=release)
    recorder = QueryRecorder(lambda: front, lambda: back, record_timeout_ms=30)
    try:
        assert recorder.insert(object()) == "timeout"
        result = recorder.front("feedback", "run", "user", "up", deadline=monotonic() + 0.8)
        assert (result.status, result.value) == ("ok", "stored")
    finally:
        release.set()
        recorder.close()
    assert front.closed and back.closed


def test_deadline_discard_and_timeout_budget():
    clock = FakeClock()
    port = FakeQueryLog(feedback="stored")
    recorder = QueryRecorder(lambda: port, clock=clock.now)
    try:
        assert recorder.front("feedback", deadline=0.3).status == "timeout"
        assert port.calls == []
        assert recorder.front("feedback", deadline=1).value == "stored"
        assert port.timeouts[-1] == 800
    finally:
        recorder.close()


def test_exception_discards_message():
    port = FakeQueryLog(feedback=ValueError("합성 질문 1"))
    with QueryRecorder(lambda: port) as recorder:
        result = recorder.front("feedback", deadline=monotonic() + 1)
        assert result.status == "failed" and "합성 질문 1" not in repr(result)


def test_factory_delay_rechecks_deadline():
    clock = FakeClock()
    port = FakeQueryLog(feedback="stored")

    def factory():
        clock.advance(0.8)
        return port

    with QueryRecorder(factory, clock=clock.now) as recorder:
        assert recorder.front("feedback", deadline=1).status == "timeout"
        assert not port.calls


def test_queued_front_job_is_discarded_after_deadline():
    from concurrent.futures import ThreadPoolExecutor

    release, started = Event(), Event()
    clock = FakeClock()
    port = FakeQueryLog(feedback=lambda: (started.set(), release.wait(2))[1])
    with QueryRecorder(lambda: port, clock=clock.now) as recorder, ThreadPoolExecutor(2) as clients:
        first = clients.submit(recorder.front, "feedback", deadline=10)
        assert started.wait(1)
        second = recorder._front.submit("feedback", (), 1)
        clock.advance(2)
        release.set()
        assert first.result(1).status == "ok"
        assert second.result(1).status == "timeout"
        assert len(port.calls) == 1


def test_completed_after_absolute_deadline_is_still_unknown():
    clock = FakeClock()

    def delayed():
        clock.advance(2)
        return "stored"

    port = FakeQueryLog(feedback=delayed)
    with QueryRecorder(lambda: port, clock=clock.now) as recorder:
        assert recorder.front("feedback", deadline=1).status == "timeout"


def test_timeout_cancels_queued_question_and_erases_reference(monkeypatch):
    import gc
    import weakref
    from datetime import date

    from qello_knowledge.query.pending import PendingQuestions

    class Question(str):
        pass

    release, started = Event(), Event()
    futures = []
    pending = PendingQuestions(retain_until=date(2026, 12, 31), today=lambda: date(2026, 10, 29))
    port = FakeQueryLog()
    recorder = QueryRecorder(lambda: port)
    submit = recorder._front.submit

    def capture(*args):
        future = submit(*args)
        futures.append(future)
        return future

    monkeypatch.setattr(recorder._front, "submit", capture)
    recorder._front.executor.submit(lambda: (started.set(), release.wait(3)))
    assert started.wait(1)
    try:
        question = Question("합성 질문 1")
        reference = weakref.ref(question)
        pending.put("run", "user", question, "answered")
        assert (
            recorder.front("store_question", "run", "user", question, deadline=monotonic() + 0.35).status == "timeout"
        )
        pending.close()
        assert len(pending) == 0
        del question
        gc.collect()
        assert reference() is None
        assert futures[0].cancelled()
    finally:
        release.set()
        recorder.close()
    gc.collect()
    assert reference() is None

    assert port.calls == []
