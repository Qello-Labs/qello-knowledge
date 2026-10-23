# Contract: 생성 경계 (`generation/`, `ports/generator.py`)

타입은 [data-model.md](../data-model.md)를 따른다. `generation/`은 `domain`·`ports`만 가져온다(경계 시험은 research R-13).

## 1. 공개 함수

```python
def generate(
    request: GenerationRequest, deps: GenerationDeps, settings: GenerationSettings | None = None
) -> GenerationResult: ...


def render(
    question: str, blocks: Sequence[ContextBlock], prompt: PromptSpec, settings: GenerationSettings
) -> RenderedInput: ...  # 순수(R-03)
def postprocess(reply_text: str, rendered: RenderedInput) -> Postprocessed: ...  # 순수(R-04)
def check_settings(gen: GenerationSettings, retrieval: RetrievalSettings) -> list[str]: ...  # spec FR-019 (1)
def prompt_spec(name: str) -> PromptSpec: ...  # gen-p1, gen-base
```

`Postprocessed`는 `answer`, `citation_ids`, `cannot_confirm_reason`, `empty`(R-04 7단계), 후처리 수치, `unsupported_answer`, `thinking_detected`를 담는다.

## 2. 경계 (`ports/generator.py`)

```python
class Generator(Protocol):  # 기존 빈 Protocol을 채운다
    def generate(self, request: GenerationRequest) -> GenerationResult: ...


class GenerationProvider(Protocol):  # 외부 호출 한 번. 재시도하지 않는다
    def complete(
        self, model_id: str, system: str, user: str, max_tokens: int, temperature: float, timeout_seconds: float
    ) -> ProviderReply: ...

    # 실패는 GenerationProviderFailure(kind, billable, neurons, tokens, shape)


class GenerationLedger(Protocol):
    def record(self, usage: GenerationUsage) -> AnswerUsageToday: ...
    def today(self) -> AnswerUsageToday: ...
    def prune(self, retention_days: int = 90) -> PruneResult: ...
```

`GenerationDeps`: `provider`, `ledger`, `outgoing_check: OutgoingCheck`(QK-EMB-001 `ports.embedder`), `retry_delay: RetryDelay`(`ports.embedder`), `sleep`, `monotonic`(지연·마감), `new_run_id`.

## 3. `generate` 처리 순서

research R-05 표 순서 그대로다. 앞 단계에서 끝나면 뒤 단계는 하지 않는다.

1. 질문 = `request.question.strip()`. 검색 결과에 질문의 외부 전송 차단(상태 또는 `omitted`)이 있으면 `outgoing_blocked`.
2. 질문을 무력화(R-03)해 `outgoing_check(question, None)`. 걸리면 `outgoing_blocked`.
3. 검색 상태가 그 밖의 실패 종류면 `retrieval_failed`(+원래 종류).
4. `no_results`면 `cannot_confirm(no_results)`, Context 묶음 0이면 `cannot_confirm(empty_context)`. 본문 `"제공된 자료만으로 확인할 수 없습니다."`, `citations = ()`.
5. 묶음마다 렌더링(R-03)하고 `outgoing_check(block.text, None)`. 걸린 묶음을 빼고 남은 묶음으로 사용자 메시지를 만든다(Source ID 유지, 다시 검사하지 않음). 남은 묶음 0이면 `cannot_confirm(all_blocks_blocked)`.
6. 호출 직전 한도 검사(R-08 (2)). 넘으면 `generation_failed(input_too_long)`, 사용량 기록 없음.
7. 시도 1~2: `provider.complete(...)`. 실패한 시도는 실패를 받은 즉시 `ledger.record(...)`(결과 종류·Neurons는 research R-06 표). 일시 실패·시간 초과면, (지난 시간 + `retry_delay(0, retry_after)` + 시간 제한)
   ≤ 마감일 때만 기다려 한 번 더. 그 밖의 실패는 바로 `generation_failed`.
8. 성공 응답이면 `postprocess`(R-04)를 하고 나서 그 시도를 기록한다. `empty`면 결과 종류 `bad_response`로 기록하고 `generation_failed(bad_response)`, 아니면 `ok`로 기록한다.
   기록 예외는 7·8단계 모두 잡아서 `usage_record_failed`를 세우고 경고 로그(원문 없음) 한 줄.
9. 결과 조립: 출처 목록은 남은 `RenderedBlock.block`(원본 `ContextBlock`)과 `raw_title`로. 잘림은 `finish_reason == "length"` 또는 (`None`이고 `output_tokens == max_tokens`).
   요약 `usage_today`는 마지막 성공한 기록 값.

## 4. 외부 호출 수

| 경로 | 생성 호출 | 사용량 기록 | 합 |
| --- | --- | --- | --- |
| 1~6단계에서 끝남 | 0 | 0 | 0 |
| 1회 성공·실패(재시도 없음) | 1 | 1 | 2 |
| 일시 실패 → 재시도 | 2 | 2 | 4 |

`total_calls = generation_calls + retrieval.summary.external_calls` ≤ 11(spec FR-024). 질문·묶음 검사는 로컬이라 세지 않는다.

## 5. 보장

| 보장 | 근거 |
| --- | --- |
| 걸린 질문·묶음은 제공자로 가지 않는다 | spec FR-010, SC-003 |
| 출처 목록의 Source ID는 보낸 묶음의 것뿐이고 값은 무력화 전 원본이다 | spec FR-011·014·016, SC-001 |
| 생성 입력에서 FR-013 규칙으로 인식되는 꼴은 머리줄의 `[S번호]`뿐이다 | spec FR-011, SC-004 |
| 사용자 메시지는 ` /no_think`로 끝난다(템플릿에서) | spec FR-018, SC-005 |
| 요약·기록·로그·예외 문구에 질문·답변·본문이 없다 | spec FR-012, SC-006 |
| 재시도는 일시 실패·시간 초과에만 1회이고 마감 안에서만, 시도마다 기록 1 | spec FR-022, SC-007 |
| 같은 입력·같은 가짜 응답이면 같은 생성 입력·결과 | spec FR-006, SC-010 |
| 호출자는 HTTP·Workers AI 고유 타입을 보지 않는다 | spec FR-001·002, C-06 |

## 6. 다른 경계에 더하는 것

| 경계 | 변경 |
| --- | --- |
| `ports/generator.py` | 빈 `Generator`를 채우고 `GenerationProvider`·`GenerationLedger` 추가 |
| `adapters/workers_ai/generation.py`(새 파일) | `WorkersAiGenerationProvider`, 생성 전용 전송(호출마다 시간 제한, 시간 초과 구분), 오류 판정(`rest.py`와 같은 규칙, 표 시험), `ResponseShape` |
| `adapters/workers_ai/rest.py` | 바꾸지 않는다. 공개 상수(`API_BASE`, `INPUT_TOO_LONG_CODE`, `QUOTA_CODE`, `NEURONS_HEADER`)만 가져다 쓴다 |
| `adapters/postgres/generation_usage.py`(새 파일) | `PostgresGenerationLedger` |
| `adapters/postgres/migrations/0006_generation_usage.sql` | data-model 6절. 추가만 |
| `config/registry.py`, 설정 예시 파일 | `QK_GEN_*` 5개(R-12) |
| `config/check.py` | `check_settings` 결과를 설정 검사 보고에 더한다 |
| `indexer/cli.py`, `indexer/ask_cli.py`(새 파일) | `qk-index ask`(contracts/cli.md) |
| `indexer/usage.py` | `prune`이 `qk.generation_usage_prune`도 부르고 결과를 함께 출력(R-06). `today` 표시는 바꾸지 않는다 |
| `tests/unit/test_boundaries.py` | `generation` 전용 위반 검사, `domain`·`ports`가 `generation`을 가져오지 않는 검사(R-13). RESTRICTED에는 넣지 않는다(넣으면 `generation` 안의 서로 가져오기가 기존 검사에 걸린다) |
