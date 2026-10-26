"""상태별 합성 결과를 실제 US1 작업·전송 경로에 넣는다."""

from qello_knowledge.domain.generation import GenerationFlags, GenerationResult, GenerationStatus, GenerationSummary
from qello_knowledge.domain.retrieval import RetrievalSummary
from tests.unit.discord.bot_builders import ask
from tests.unit.query.bot_runtime import bot_request, bot_runtime
from tests.unit.query.test_bot_pipeline import bot_pipeline


def bot_result(
    status=GenerationStatus.ANSWERED,
    *,
    answer="합성 답변",
    citations=(),
    flags=None,
    failure=None,
    retrieval_failure=None,
):
    return GenerationResult(
        status,
        answer,
        tuple(citations),
        GenerationSummary(
            status, failure=failure, retrieval_failure=retrieval_failure, flags=flags or GenerationFlags()
        ),
        RetrievalSummary(),
    )


def bot_run_result(result, *, private=False, **options):
    runtime = bot_runtime(**options)
    pipeline, _, _, _, _ = bot_pipeline(runtime.clock)
    pipeline._generate = lambda request, deps, settings: result
    runtime.jobs._pipeline = pipeline
    body = ask("합성 질문 표식", private=private)
    signature = runtime.key.sign(body, "1000")
    runtime.first_response = bot_request(runtime, body, headers=signature)
    _, _, headers = runtime.first_response
    run_id = headers["X-QK-Run"]
    assert runtime.jobs.start(run_id, signature["X-Signature-Ed25519"], "1000")
    runtime.jobs.poll()
    runtime.compute.run_next()
    runtime.deliveries.run_next()
    return runtime, run_id
