from concurrent.futures import ThreadPoolExecutor
from dataclasses import fields
from threading import Barrier, Event, Lock

from qello_knowledge.discord.interactions import parse
from qello_knowledge.domain.discord import DedupStage, QueryStage, RenderedReply
from tests.unit.discord.bot_builders import ask
from tests.unit.query.bot_runtime import bot_runtime


def bot_reserve(runtime, number):
    item = parse(ask("합성 질문", interaction_id=str(number)))
    return runtime.jobs.reserve(item, "synthetic-signature", "1000")


def test_bot_lifetime_capacity_dedup_expiry_and_restart():
    runtime = bot_runtime()
    accepted = [bot_reserve(runtime, n) for n in range(6)]
    assert all(r.type == 5 for r in accepted)
    assert "지금 요청이 많습니다" in bot_reserve(runtime, 6).data["content"]
    assert "이미 처리 중" in bot_reserve(runtime, 0).data["content"]
    entry = runtime.jobs.dedup["0"]
    assert {f.name for f in fields(entry)} == {"interaction_id", "stage", "expires_at"}
    runtime.clock.advance(5)
    runtime.jobs.poll()
    assert len(runtime.deliveries.pending) == 6 and not runtime.fake.requests
    for _ in range(6):
        runtime.deliveries.run_next()
    assert runtime.jobs.in_flight == 0 and runtime.jobs.dedup["0"].stage is DedupStage.DONE
    assert "이미 처리 중" in bot_reserve(runtime, 0).data["content"]
    runtime.clock.advance(895)
    assert bot_reserve(runtime, 0).type == 5
    assert bot_reserve(bot_runtime(), 0).type == 5


def test_bot_concurrent_duplicates_reserve_only_one_slot():
    runtime = bot_runtime()
    barrier = Barrier(2)

    def reserve():
        barrier.wait()
        return bot_reserve(runtime, 1).type

    with ThreadPoolExecutor(2) as pool:
        a, b = pool.submit(reserve), pool.submit(reserve)
        assert sorted((a.result(), b.result())) == [4, 5]
    assert runtime.jobs.in_flight == 1


def test_bot_queue_min_start_time_and_delivery_claim_only_once():
    runtime = bot_runtime()
    response = bot_reserve(runtime, 1)
    assert runtime.jobs.start(response.run_id, "synthetic-signature", "1000")
    runtime.clock.advance(41)
    runtime.jobs.poll()
    assert runtime.jobs.outcome(response.run_id) is QueryStage.TIMED_OUT
    assert not runtime.compute.pending and len(runtime.deliveries.pending) == 1
    runtime.jobs.poll()
    assert len(runtime.deliveries.pending) == 1
    runtime.deliveries.run_next()
    assert runtime.jobs.stage(response.run_id) is QueryStage.DONE


def test_bot_two_late_executions_keep_their_slots_until_actual_return():
    entered = [Event(), Event()]
    release = Event()
    calls = []

    def pipeline(job, stage):
        index = len(calls)
        calls.append(job.run_id)
        if index < 2:
            entered[index].set()
            assert release.wait(0.8)
        return RenderedReply(("합成 답변",), False)

    runtime = bot_runtime(pipeline=pipeline)
    executor = ThreadPoolExecutor(2)
    runtime.jobs._executor = executor
    try:
        for n in range(2):
            response = bot_reserve(runtime, n)
            runtime.jobs.start(response.run_id, "synthetic-signature", "1000")
        runtime.jobs.poll()
        assert all(event.wait(0.3) for event in entered)
        runtime.clock.advance(55)
        runtime.jobs.poll()
        for _ in range(2):
            runtime.deliveries.run_next()
        for n in range(2, 8):
            response = bot_reserve(runtime, n)
            runtime.jobs.start(response.run_id, "synthetic-signature", "1000")
        runtime.jobs.poll()
        assert len(calls) == 2 and runtime.jobs.running == 2 and runtime.jobs.in_flight == 6
        assert bot_reserve(runtime, 8).type == 4
    finally:
        release.set()
        runtime.jobs.close()
        executor.shutdown(wait=True)
    assert len(runtime.fake.requests) == 2  # 늦은 답변은 두 번째 전달을 만들지 않는다.


def test_bot_expired_queued_ids_do_not_accumulate_behind_late_calls():
    runtime = bot_runtime()
    for n in range(2):
        response = bot_reserve(runtime, n)
        runtime.jobs.start(response.run_id, "synthetic-signature", "1000")
    runtime.jobs.poll()  # 가짜 실행기에서 아직 반환되지 않은 실행 두 개
    for cycle in range(5):
        runtime.clock.advance(55)
        runtime.jobs.poll()
        while runtime.deliveries.pending:
            runtime.deliveries.run_next()
        for n in range(6):
            response = bot_reserve(runtime, 10 + cycle * 6 + n)
            assert response.type == 5
            runtime.jobs.start(response.run_id, "synthetic-signature", "1000")
        runtime.jobs.poll()
        assert len(runtime.jobs._queue) <= runtime.jobs.capacity


def test_bot_six_expirations_get_delivery_slots_without_waiting_for_previous_delivery():
    from qello_knowledge.adapters.discord.webhook import DiscordWebhook
    from tests.unit.discord.bot_builders import APPLICATION, FakeClock, FakeDiscord

    runtime = bot_runtime()
    pool = ThreadPoolExecutor(6)
    entered, release = Event(), Event()
    lock = Lock()
    started, finished = [], []

    def deliver(job, reply):
        with lock:
            started.append(job.run_id)
            if len(started) == 6:
                entered.set()
        assert release.wait(0.8)
        clock = FakeClock(5)
        fake = FakeDiscord([(429, {"retry_after": 2}), (200, {}, 2)], clock=clock)
        result = DiscordWebhook(APPLICATION, transport=fake, clock=clock.now, sleep=clock.advance).deliver(
            job.interaction.token, reply, deadline=job.notice_deadline
        )
        with lock:
            finished.append((clock.now(), result))
        return result

    runtime.jobs._delivery_executor = pool
    runtime.jobs._deliver = deliver
    try:
        for n in range(6):
            bot_reserve(runtime, n)
        runtime.clock.advance(5)
        runtime.jobs.poll()
        assert entered.wait(0.3) and runtime.jobs.in_flight == 6
        assert bot_reserve(runtime, 7).type == 4
    finally:
        release.set()
        pool.shutdown(wait=True)
        runtime.jobs.close()
    assert len(finished) == 6 and all(at <= 60 and r.stage is QueryStage.DONE for at, r in finished)
    assert runtime.jobs.in_flight == 0
