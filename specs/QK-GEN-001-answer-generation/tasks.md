---
description: "QK-GEN-001 구현 작업 목록"
---

# Tasks: QK-GEN-001 답변 생성 프롬프트·출처 표시·확인 불가·충돌 처리·생성 Provider

**Input**: `specs/QK-GEN-001-answer-generation/`의 plan.md, spec.md, research.md(R-01~R-14, 검토 반영 2회), data-model.md, contracts/generation.md, contracts/cli.md, quickstart.md

**Tests**: 포함한다. 명세의 수용 시나리오와 C-12가 자동 시험을 요구한다. 시험을 먼저 쓰고 실패를 확인한 뒤 구현한다. 모든 자동 시험은 외부 호출 0건이다(가짜 생성 제공자 `generation/fake.py`의
`ScriptedProvider`, 메모리 장부 `MemoryLedger`, 가짜 전송, 가짜 임베딩 제공자 `embedding/fake.py`, 로컬 DB). 실제 Workers AI 호출은 맨 끝 "사람 단계"다.

**Organization**: 사용자 스토리별 단계. US1 → US2 → US3 → US4(모두 P1) → US5 → US6(P2) → US7(P3). US2~US4는 US1의 `generation/service.py`·`postprocess.py`·`render.py`를 넓혀 나간다.
커밋은 스토리 단위로 나눈다(`/harness-commit`).

**선행 조건**: spec.md·plan.md 사람 승인(2026-10-23), 이 목록의 사람 승인, `TASK.md` Scope를 구현 범위로 갱신(plan.md "구현 Scope 승인이 필요한 것" 표 포함, AGENTS.md 1절).

**공통 규칙**:
- 질문 원문, 답변 본문, 청크 본문, 생성 입력 전체, 비밀값, 접속 주소를 로그·예외 문구·요약·사용량 기록에 넣지 않는다(spec FR-012). 시험은 이 규칙을 검사한다(T030).
  확인 명령의 표준 출력에는 답변 본문과 출처 목록만 낸다(research R-10).
- 시험용 합성 문서만 쓴다. 대상 저장소 원문과 실제 팀 질문을 저장소에 복사하지 않는다(AGENTS.md 6절). 시험을 지우거나 `skip`·`xfail`로 체크포인트를 통과시키지 않는다.
- 로컬 DB 시험은 `tests/localdb/` 아래에 두고 QK-STO-001 방식(세션마다 `qk_test_<무작위>` 데이터베이스 생성·마이그레이션·삭제)을 따른다. 공유 `postgres` 데이터베이스는 건드리지 않는다.
- 기존 코드는 plan.md Scope 표의 변경만 한다. `adapters/workers_ai/rest.py`, 기존 `qk.embedding_*` 테이블·함수, `retrieval/`, `query/app.py`는 바꾸지 않는다. 기존 시험은 바꾸지 않고 그대로 통과해야 한다.
  예외는 T043의 `tests/unit/indexer/test_cli_usage.py` prune 시험 기대 출력 갱신과 가짜 생성 장부 주입뿐이다(2026-10-23 사용자 결정, 검사 내용은 그대로).
- 새 시험 파일 이름은 `tests/` 전체에서 겹치지 않게 `test_gen_` 접두어를 붙인다(시험 디렉터리에 `__init__.py`가 없어 같은 이름이면 pytest 수집이 실패한다. `test_settings.py`·`test_usage.py`는 이미 있다).
- `generation/`은 표준 라이브러리와 `qello_knowledge.domain`·`ports`·`generation`만 가져온다(T002). 상대 경로 가져오기를 쓰지 않는다. 외부 호출은 `ports/generator.py`의 경계와
  `ports/embedder.py`의 `OutgoingCheck`·`RetryDelay`만 거친다.

**TDD 순서**: 각 단계에서 시험 작업을 먼저 쓰고 실패(아직 없는 모듈이면 수집 오류 포함)를 확인한 뒤 구현 작업을 한다. [P]는 같은 단계의 시험끼리, 구현끼리 병렬이라는 뜻이다.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: 다른 파일을 다루고 미완료 작업에 기대지 않아 병렬로 할 수 있다
- **[Story]**: 해당 사용자 스토리(US1~US7)

---

## Phase 1: Setup

- [X] T001 패키지 자리 만들기: `src/qello_knowledge/generation/__init__.py`, `tests/unit/generation/`(골든 파일 자리 `tests/unit/generation/golden/` 포함), `specs/QK-GEN-001-answer-generation/measurement/`,
  `tests/localdb/generation/conftest.py`. conftest는 `tests/localdb/retrieval/conftest.py:20-33` 꼴을 따른다: `pytestmark = pytest.mark.localdb`, `db_url`(`tests/localdb/store/conftest.py` 방식), 시험마다
  `qk.generation_usage`·`qk.generation_usage_daily`·`qk.embedding_usage`·`qk.embedding_usage_daily`를 비우는 자동 픽스처, `store` 픽스처, `seed_index_versions`·`seed_doc` 도우미(활성 인덱스 없음 사례를 만들 수 있게).
  시험 디렉터리에는 `__init__.py`를 만들지 않는다
- [X] T002 [P] `tests/unit/test_boundaries.py`: 기존 `RESTRICTED`·`ALLOWED_INTERNAL`·검사 함수는 그대로 두고, `generation` 전용 허용 목록(`domain`·`ports`·`generation`)과 검사 함수를 따로 더한다
  (QK-RET-001 `retrieval` 검사와 같은 꼴). 위반 사례 시험: `generation/`이 `qello_knowledge.adapters`·`security`·`retrieval`·`indexer`·`psycopg`를 가져오면 실패, 상대 경로 가져오기(`from . import x`,
  `from ..adapters import y`)면 실패, `domain`·`ports`가 `qello_knowledge.generation`을 가져오면 기존 검사가 실패. RESTRICTED에 `generation`을 넣지 않는다(넣으면 `generation` 안의 서로 가져오기가 기존 검사에 걸린다.
  research R-13·contracts 6절도 이에 맞춰 고쳤다, 독립 검토 L10)

---

## Phase 2: Foundational

**목적**: 모든 스토리가 쓰는 타입·설정·프롬프트·경계·가짜 구현. 이 단계가 끝나야 스토리 시험을 쓸 수 있다.

- [X] T003 [P] `tests/unit/generation/test_gen_settings_domain.py`(data-model 1절, spec FR-025): `GenerationSettings` 기본값(모델 `@cf/qwen/qwen3-30b-a3b-fp8`, 출력 800, 온도 0.2, 시간 제한 20, 프롬프트 `gen-p1`,
  바이트당 토큰 3.5, 배율 2.0, 창 32,768, 입력 단가 4,625, 출력 단가 30,475, 시도 2, 마감 `2 × timeout_seconds + 5` = 45)과 범위("모델 `@cf/qwen/qwen3-` 접두어", "출력 1~4,096", "온도 0~1",
  "시간 제한 1~60", "배율 1.0~4.0", "마감을 직접 주면 `2 × timeout_seconds + 2` 이상 ~ 130", "단가 > 0") 안·밖, `PROMPT_NAMES = ("gen-p1", "gen-base")`에 없는 프롬프트 이름 거부
  (이름 목록은 `domain`에 둔다. `domain`이 `generation`을 가져오지 않게, 독립 검토 M3). 시간 제한 30이면 마감 기본값 65
- [X] T004 [P] `tests/unit/generation/test_gen_domain.py`(data-model 2~5절): 원문 필드(`question`, `system`, `user`, `text`, `answer`)가 `repr`에 나오지 않음, `GenerationStatus` 값 5개
  (`answered`, `cannot_confirm`, `retrieval_failed`, `outgoing_blocked`, `generation_failed`), `GenerationFailure` 6개(`transient`, `timeout`, `provider_quota`, `auth_config`, `bad_response`, `input_too_long`),
  `CannotConfirmReason` 5개(`no_results`, `empty_context`, `all_blocks_blocked`, `model_cannot_confirm`, `model_unconfirmable_parts`), `GenerationResult` 불변식("`status == cannot_confirm`이면 `citations == ()`",
  "`flags.unsupported_answer`이면 `status == answered`이고 `citations == ()`") 위반 시 생성 실패
- [X] T005 `src/qello_knowledge/domain/generation.py`: data-model 1~5절을 표준 라이브러리 불변 dataclass·`StrEnum`으로 정의한다. `PROMPT_NAMES`, `GenerationSettings`(생성 때 `ValueError`), `PromptSpec`, `GenerationRequest`,
  `RenderedBlock`(`source_id`, `block: ContextBlock`, `raw_title`, `title`, `modified_label`, `text`, `excerpt_urls: frozenset[str]`, `estimated_tokens`), `DroppedBlock`, `RenderedInput`, `ResponseShape`, `ProviderReply`,
  `GenerationStatus`, `GenerationFailure`, `CannotConfirmReason`, `Citation`, `GenerationFlags`, `GenerationSummary`, `GenerationResult`, `GenerationUsage`, `AnswerUsageToday`. T003·T004 통과
- [X] T006 `src/qello_knowledge/ports/generator.py`: 빈 `Generator`를 채우고 `GenerationProvider`, `GenerationLedger`, 예외 `GenerationProviderFailure`(`kind: GenerationFailure`, `retry_after_seconds`, `billable`,
  `neurons`, `input_tokens`, `output_tokens`, `shape`. 메시지는 종류 값만)를 contracts/generation.md 2절대로 정의한다
- [X] T007 [P] `tests/unit/generation/test_gen_prompts.py`(research R-02, spec FR-003·005, SC-010): 승인 원문을 고정 파일 `tests/unit/generation/golden/gen-p1-system.txt`·`gen-p1-template.txt`·
  `gen-base-system.txt`·`gen-base-template.txt`로 두고(코드 블록 안 글 그대로, 끝 줄바꿈 없음, UTF-8), `prompt_spec(...)`의 글이 그 파일과 글자 그대로 같음. 고정 파일을 만들 때 한 번만 `TASK.md`
  "승인된 입력"·spike 부록 B·research R-02와 대조하고 그 사실을 실행 기록에 남긴다(시험은 `TASK.md`를 읽지 않는다. TASK.md는 브랜치마다 바뀐다, 독립 검토 H3). 두 템플릿이 ` /no_think`로 끝남,
  식별자 꼴 `<이름>-<12자 16진>`, 시스템·템플릿·렌더링 규칙 중 하나만 바꾼 `PromptSpec`의 식별자가 모두 다름, 해시 재료가 `json.dumps(..., ensure_ascii=False, sort_keys=True)`, `prompts.py`의 이름 집합 = `domain` `PROMPT_NAMES`
- [X] T008 `src/qello_knowledge/generation/prompts.py`: `gen-p1`(render-v1)·`gen-base`(render-base) 상수와 `prompt_spec`, 식별자 계산. T007 통과
- [X] T009 `src/qello_knowledge/generation/fake.py`(T005·T006 뒤): `ScriptedProvider`(호출 순서대로 `ProviderReply` 또는 `GenerationProviderFailure`를 돌려주고 받은 `(system, user, max_tokens, temperature, timeout_seconds)`를 기록),
  `MemoryLedger`(`record`가 `AnswerUsageToday`를 돌려줌, 실패 주입 옵션). 질의 임베딩 사용량은 생성자 인자로 받는다
- [X] T010 [P] `tests/unit/generation/test_gen_check_settings.py`(spec FR-019 (1), research R-08, SC-009): 기본 설정 통과(계산값 10,650 ≤ 32,768), Context 예산 8,000·질문 상한 8,000자면 거부,
  질문 상한을 "한 글자 4바이트"로 바꾸는지, 배율을 입력에만 곱하는지, 출력 상한을 그대로 더하는지
- [X] T011 `src/qello_knowledge/generation/settings.py`: `check_settings(gen, retrieval) -> list[str]`(문제 문장 목록, 원문 없음)과 `estimate_tokens(text, settings)`(`ceil(UTF-8 바이트 ÷ bytes_per_token)`). T010 통과

**Checkpoint**: 타입·프롬프트·설정 검사·가짜 구현 준비 완료

---

## Phase 3: User Story 1 - 근거가 있는 질문에 출처가 붙은 한국어 답을 받는다 (P1) 🎯 MVP

**Goal**: 정상 경로. Context를 render-v1로 렌더링해 가짜 제공자에 보내고, 인용을 인식해 출처 목록과 요약을 돌려준다.

**Independent Test**: 고정 Context(S1·S2·S3)와 정해 둔 가짜 답변으로 `generate`를 불러 생성 입력·본문·출처 목록·요약을 본다(spec US1).

- [X] T012 [P] [US1] `tests/unit/generation/test_gen_render.py`(research R-03, spec FR-004·006): render-v1 머리줄 `[S1] A > B | 수정 2026-10-10`(UTC 2026-10-09T16:00Z가 한국 날짜 10-10이 되는 사례 포함),
  수정 시각 없음 → `수정 미상`, 빈 제목 경로 → 청크 위치 경로 → `제목 없음`, `gaps`마다 `…(중간 생략)…` 줄, 같은 묶음 안 제목 경로가 바뀌면 `(절: A > C)` 줄, 묶음 사이 빈 줄 하나, 사용자 메시지가 템플릿 그대로이고
  ` /no_think`로 끝남(따로 붙이지 않음), 같은 입력 두 번 바이트 일치, 고정 Context 3종 골든 비교(`tests/unit/generation/golden/`의 합성 기대 파일)
- [X] T013 [P] [US1] `tests/unit/generation/test_gen_happy_path.py`(spec US1 1~5, FR-016·026): S1·S2 인용 답 → `answered`, 출처 목록 S1·S2 번호 순서이며 제목·링크·버전·수정 시각·수집 시각이 원본 `ContextBlock` 값,
  S1만 인용 → 목록 S1만, 요약에 프롬프트 버전·모델·출력 상한·온도·추론 끔·보낸 묶음 수·예상 입력 토큰·제공자 토큰·Neurons·시도·지연·호출 수(생성 2, 질의 전체 = 검색 `external_calls` + 2),
  같은 입력으로 `generate`를 두 번 불러 생성 입력과 결과가 같음(가짜 `monotonic`·`new_run_id` 고정, SC-010, 독립 검토 L4)
- [X] T014 [US1] `src/qello_knowledge/generation/render.py`: render-v1·render-base 렌더링(무력화는 US4에서 더한다), `RenderedBlock` 생성(원본 `block`·`raw_title`·`excerpt_urls`), 예상 토큰. T012 통과
- [X] T015 [US1] `src/qello_knowledge/generation/postprocess.py` 1차: research R-04 6단계 인용 인식(`\[[ \t]*S([1-9]\d*)([ \t]*[,，][ \t]*S([1-9]\d*)|[ \t]+S([1-9]\d*))*[ \t]*\]`)과 `[S1][S2]` 정규화, 생성 입력에 없는 ID 제거,
  11단계 출처 목록 ID. 나머지 단계는 US2·US3에서 더한다
- [X] T016 [US1] `src/qello_knowledge/generation/service.py` 1차: `GenerationDeps`, `generate`의 정상 경로(contracts/generation.md 3절 5~9단계 가운데 렌더링·호출 1회·기록·후처리·결과 조립), 출처 목록을 `RenderedBlock.block`과
  `raw_title`로 만듦, 요약. 제공자 실패는 이 단계에서 재시도 없이 `generation_failed(<종류>)`와 시도 기록 1건으로 돌려준다(재시도·마감·R-06 Neurons는 T039, 독립 검토 M2). `generation/__init__.py`에서 `generate`·`render`·`postprocess`·`check_settings`·`prompt_spec` 공개. T013 통과

**Checkpoint**: 가짜 제공자로 출처 붙은 답 생성

---

## Phase 4: User Story 2 - 자료에 근거가 없으면 "확인할 수 없습니다"로 답한다 (P1)

**Goal**: 생성 호출 없는 판정(research R-05 3~5)과 모델 확인 불가 판정(FR-009 가·나·다), 빈 결과.

**Independent Test**: 검색 상태별 결과와 확인 불가 꼴의 가짜 답으로 상태·본문·호출 수를 본다(spec US2).

- [X] T017 [P] [US2] `tests/unit/generation/test_gen_no_call.py`(spec US2 1·2, FR-007·008, SC-002): `no_results`·빈 Context에서 제공자 호출 0, 본문이 `"제공된 자료만으로 확인할 수 없습니다."`와 글자 일치,
  `citations == ()`, 사유 `no_results`·`empty_context`. 검색 실패 종류마다(`empty_question`, `question_too_long`, `no_active_index`, `store_unavailable`, `index_version_changed`, `query_embedding_failed`,
  `keyword_search_failed`, `both_searches_failed`) `retrieval_failed`와 원래 종류, 호출 0
- [X] T018 [P] [US2] `tests/unit/generation/test_gen_cannot_confirm.py`(spec US2 3~5, FR-009, research R-04 7·8단계): (가) 공백·따옴표·인식된 인용(`[S1]`)이 붙은 확인 불가 문장·끝 마침표 없는 문장·같은 문장 두 번 → `cannot_confirm`
  (`model_cannot_confirm`), 본문은 확인 불가 문장 하나. (나) "○○은 … 확인할 수 없습니다." 문장들만, 확인 불가 + "현재 상태는 원본에서 확인해야 합니다." → `cannot_confirm`(`model_unconfirmable_parts`), 본문 유지·인용
  제거·출처 비움. (나) 고정 사례: `재시도는 3회이며 나머지는 제공된 자료만으로 확인할 수 없습니다 [S1].` → `cannot_confirm`, 출처 비움(2026-10-23 사용자 결정, research R-04 남는 위험). (다) 유효 인용 문장 + 확인 불가 부분 → `answered`.
  빈 결과: 빈 글, 공백만 → `generation_failed(bad_response)`. 1~4단계가 있어야 하는 사례(`(S1)`이 붙은 확인 불가 문장, `출처: [S1]` 한 줄만, 발췌문에 없는 URL 하나만, 추론 블록만)는 US3의 T024에 둔다
  (US2 체크포인트가 빨갛게 남지 않게, 독립 검토 M1)
- [X] T019 [US2] `generation/service.py`: research R-05 3~5단계 판정(검색 실패 → 결과 없음 → 빈 Context)을 렌더링·호출 앞에 둔다. T017 통과
- [X] T020 [US2] `generation/postprocess.py`: R-04 5단계 문장 나누기(마침표·물음표·느낌표 뒤 공백·줄 끝, 줄바꿈, 점 뒤 공백 없는 `5.5`·`a.py`는 경계 아님, 조각 머리 인용을 문장부호로 끝난 앞 조각으로 옮김, 인용만 남은 조각은 앞에 붙임,
  빈 조각 버림), 7단계 빈 결과, 8단계 (가)(나)(다) 판정. `generation/service.py`가 빈 결과를 `bad_response`로. T018 통과

**Checkpoint**: 확인 불가와 무호출 경로 완료

---

## Phase 5: User Story 3 - 답변의 출처 표기를 코드가 검사하고 출처 목록은 코드가 만든다 (P1)

**Goal**: research R-04 1~11단계 전체.

**Independent Test**: 없는 ID, 여러 ID 표기, 인식 못 하는 꼴, URL, 출처 줄, 코드 표기를 섞은 가짜 답으로 본문·출처 목록·요약 수치를 본다(spec US3).

- [X] T021 [P] [US3] `tests/unit/generation/test_gen_citations.py`(spec FR-013·014·015, SC-001): `[S9]` 제거·`removed_citations` 1, `[S1, S2]`·`[S1，S2]`·`[ S1 ]`·`[S1 S2]` → `[S1][S2]`, 같은 문장 안 `[S1][S1]` → `[S1]`,
  `[S1, S9]` → `[S1]`, 인식 못 한 꼴(`[S9,]`, `[S1；S2]`, `[S1/S2]`, `[S1 및 S2]`, `[S1, S3-S5]`, `[S1–S3]`, `[S0]`, `[S01]`, `[s1]`, `(S1)`, `【S1】`)은 남고 `unrecognized_citations`로 셈,
  `[AWS S3 버킷]`·`[S3 설정 참고]`는 세지 않음, 코드 span·코드 블록 안 `[S9]`는 지우지도 세지도 않음, `A다. [S1] B다. [S2]`의 귀속, `…잡는다.[S3] 다음`의 나눔, 유효 인용 0 → `unsupported_answer`·빈 출처 목록,
  인용 없는 문장 수(코드 블록 줄은 세지 않음), 불변식 "출처 ID = 코드 밖 인식된 인용 ID 집합"
- [X] T022 [P] [US3] `tests/unit/generation/test_gen_cleanup.py`(research R-04 1~4단계): `<think>…</think>` 여러 개·닫히지 않은 `<think>`·짝 없는 `</think>` 제거와 `thinking_detected`(안에 글이 있을 때만), 닫히지 않은 코드 펜스는 끝까지 코드,
  출처 줄(`출처:`, `참고：`, `Sources:`, `References:`와 아래 목록 줄) 제거·`removed_source_lines`, `참고로 배포는 …다 [S1].`는 남음, URL: 발췌문과 같은 URL 남음, `…/deploy에 있다` → URL과 조사 남음,
  끝 마침표 붙은 URL 남음, `https://docs.example.test`(발췌문 URL의 앞부분) 지움, 발췌문 `…/docs/설계.md`일 때 `…/docs/가짜.md` 지움, 괄호 경로 `…/Foo_(bar)` 비교, 코드 안 URL 그대로, `removed_urls`
- [X] T023 [US3] `generation/postprocess.py`: R-04 1~4단계(추론 블록, 코드 가림을 10단계까지 유지, 출처 줄, URL 규칙)와 9~10단계(세기, 코드 되돌림), 6단계 인식 못 한 꼴 셈(대괄호 안이 `S`+숫자와 공백·`,，;；/-~–`·`및`뿐인 글,
  `(S숫자)`·`【S숫자】`·`[s숫자]`). 단계 순서는 research R-04 1~11 그대로. T021·T022 통과
- [X] T024 [US3] `tests/unit/generation/test_gen_cannot_confirm_cleanup.py`: 후처리 1~6단계를 거쳐야 하는 확인 불가·빈 결과 사례. 인식 못 한 꼴이 붙은 확인 불가 문장(`… 없습니다 (S1).`) → (가),
  `출처: [S1]` 한 줄만·발췌문에 없는 URL 하나만·추론 블록만 → `generation_failed(bad_response)`. T023 뒤 통과(T018에서 옮긴 사례, 독립 검토 M1)

**Checkpoint**: 후처리 전체 완료

---

## Phase 6: User Story 4 - 비밀값과 문맥 속 지시문이 생성 경로를 넘지 못한다 (P1)

**Goal**: research R-03 무력화, R-05 1·2·6단계(질문·묶음 전송 직전 검사), 원문 비기록.

**Independent Test**: 비밀값 규칙에 걸리는 질문·묶음, 구분자를 심은 청크·질문으로 가짜 제공자가 받은 입력·호출 수·기록을 본다(spec US4).

- [X] T025 [P] [US4] `tests/unit/generation/test_gen_neutralize.py`(spec FR-011, SC-004): 청크 본문·제목 경로·청크 위치·질문에 `[자료 시작]`, `[자료 끝]`, `[자료]`, `[질문]`, `[S7]`, `[S1, S2]`, `[S1,\nS2]`, `[\nS7\n]`,
  `[[S1]]`, `[S1 [S2]`, ` | `를 심었을 때 사용자 메시지 안 구분자가 템플릿 위치 말고 0개, FR-013 인식 꼴이 머리줄 `[S번호]` 말고 0개(시스템 프롬프트는 검사 대상 아님, research R-03 SC-004 범위),
  바꾼 개수 `neutralized`, 출처 목록 제목은 무력화 전 값
- [X] T026 [P] [US4] `tests/unit/generation/test_gen_outgoing.py`(spec FR-010, US4 1~3, SC-003): `OutgoingCheck` 가짜가 걸리게 한 질문 → `outgoing_blocked`, 제공자 호출 0, 결과·요약에 질문 없음. 검색 상태 `outgoing_blocked`와
  `omitted`에 `outgoing_blocked`(하이브리드)도 같은 결과. `no_results`이면서 걸리는 질문 → `outgoing_blocked`(판정 순서, research R-05). S1·S2·S3 중 S2만 걸림 → 보낸 입력에 S2 없음, S1·S3 그대로, `dropped`에 S2와 규칙 이름,
  모두 걸림 → `cannot_confirm(all_blocks_blocked)`, 호출 0. 검사는 질문 1회 + 묶음마다 1회, 출처 인자는 모두 `None`, 검사 대상은 무력화·렌더링 뒤 글(머리줄 포함).
  하이브리드 검색이 한쪽을 생략한 결과(`omitted`에 `query_embedding_failed`·`vector_search_failed`·`keyword_search_failed`)는 남은 Context로 생성하고 검색 요약에 생략 사유가 그대로 남음(spec Edge Cases, 독립 검토 L5)
- [X] T027 [US4] `generation/render.py`: R-03 무력화(`\[[^\[\]]*?S\d[^\[\]]*?\]` DOTALL과 구분자 표기의 대괄호를 전각 `［`·`］`로, 제목·위치의 ` | `를 ` ¦ `로, 개수 셈). T025 통과
- [X] T028 [US4] `generation/service.py`: R-05 1·2단계(질문 `strip`·무력화·검사)를 판정 맨 앞에, 6단계(묶음별 검사·빼기·0이면 확인 불가)를 렌더링 뒤에 둔다(contracts/generation.md 3절 순서). T026 통과
- [X] T029 [P] [US4] `tests/unit/generation/test_gen_injection_prompt.py`(spec US4·US5, C-03): `gen-p1` 시스템 프롬프트에 규칙 7(지시 무시)·규칙 5(충돌)·규칙 6(현재 상태)·규칙 3(확인 불가 문장)이 들어 있고, 자료 블록이
  `[자료 시작]`·`[자료 끝]` 사이, 질문이 `[질문]` 아래에 있음. 모델 동작 자체는 사람 단계 H02에서 본다
- [X] T030 [US4] `tests/unit/generation/test_gen_no_raw_text.py`(spec FR-012, SC-006): 표식 문자열(질문·청크 본문·모델 답에 각각 다른 무작위 표식)을 넣고, 이 단계까지 있는 상태 경로(정상, 확인 불가, 검색 실패, 전송 차단,
  재시도 없는 제공자 실패)에서 `GenerationSummary`·`GenerationUsage`·`MemoryLedger` 기록·`caplog`의 모든 로그·예외 문구에 표식이 0건. 재시도·기록 실패 경로는 T039 뒤 T039a에서 같은 시험 파일에 더한다(독립 검토 M2)

**Checkpoint**: P1 스토리(US1~US4) 전부 통과. QK-BOT-001이 쓸 생성 경계 완성

---

## Phase 7: User Story 5 - 자료가 충돌하거나 현재 상태를 물을 때 단정하지 않는다 (P2)

**Goal**: 수정일 머리줄과 프롬프트 규칙으로 충돌·현재 상태를 다루고, 실측 스크립트를 준비한다(SC-008은 사람 단계).

**Independent Test**: render-v1·render-base 출력과 실측 스크립트의 가짜 제공자 실행을 본다. 실제 모델 판정은 H02·H03.

- [ ] T031 [P] [US5] `tests/unit/generation/test_gen_base_render.py`(research R-02·R-03): render-base 묶음 `[S1] 제목: <제목>` 다음 줄에 청크 본문, 수정일·생략·절 줄 없음, 무력화 같음, `gen-base` 템플릿 `[자료]`·`[질문]` 꼴
- [ ] T032 [US5] `generation/render.py`: render-base 완성. T031 통과
- [ ] T033 [P] [US5] `tests/unit/generation/test_gen_measure_script.py`: 스크립트를 `importlib.util.spec_from_file_location`으로 불러(경로에 하이픈이 있어 일반 import 불가) 제공자 팩토리 주입 자리에 가짜 제공자를 넣고 실행한다.
  질문 세트 `gen-ko-v1`이 12문항(spike-ko-v0 생성 5 + 충돌 2·현재 상태 2·일부만 답 1·지시문 주입 1·무관 1)이고 모두 합성 문서, `--only 1 --prompt gen-p1`이 1문항·후보 1만 실행, 출력에 문항별 상태·후처리 전 수치
  (지운 인용·인식 못 한 꼴·인용 없는 문장)·문장마다 인용 비율·응답 꼴·지연·Neurons, 프롬프트별 지연 p50·p95, C-13 메타데이터(질문 세트 `gen-ko-v1`, 모델, 프롬프트 버전, 날짜, 표본 수)가 있음(독립 검토 L7),
  답변 원문은 `--out` 경로에만 쓰임, `--out` 기본이 저장소 밖(OS 임시 폴더), `--out`이 저장소 안이면 거부, `--provider workers-ai`일 때만 실제 제공자 팩토리를 부르고 그 전에 예상 Neurons와 최대치를 표준 오류로 보임
- [ ] T034 [US5] `specs/QK-GEN-001-answer-generation/measurement/measure_generation.py`(research R-11): `gen-ko-v1` 합성 Context·질문을 코드 안에 두고 생성 경계를 직접 부른다(임베딩·DB 없음, `MemoryLedger`).
  `--provider {fake,workers-ai}`(기본 `fake`), `--only N`, `--prompt {gen-p1,gen-base,both}`(기본 `both`. H01은 `--prompt gen-p1`을 명시한다), `--out`, 제공자 팩토리 주입 자리(`main(argv, provider_factory=None)`).
  실제 제공자(T036 `WorkersAiGenerationProvider`, US6에 기댐)는 `.env`에서 계정·토큰을 읽되 값은 출력하지 않는다. T033 통과(가짜 제공자 경로만. 실제 제공자 경로는 T036 뒤에 쓰인다)

**Checkpoint**: 실측 준비 완료(실행은 H01·H02)

---

## Phase 8: User Story 6 - 생성 사용량을 기록하고 실패를 구분해 돌려준다 (P2)

**Goal**: Workers AI REST 제공자, 재시도·마감, 과금 분류표, 사용량 표(0006)와 저장소 장부, 보관 정리, 설정 환경값.

**Independent Test**: 가짜 전송·가짜 제공자로 실패를 주입해 기록·재시도·결과를 보고, 로컬 DB로 0006 함수와 합계를 본다(spec US6).

- [ ] T035 [P] [US6] `tests/unit/adapters/test_gen_workers_ai_generation.py`(research R-01·R-06): 가짜 `GenerationTransport`로 요청 본문(`messages` 두 개, `max_tokens`, `temperature`)과 주소(`rest.py` `API_BASE`), 호출마다
  시간 제한 전달, 응답 꼴 (a) `result.response`+`usage`와 (b) `choices[0].message.content`+`finish_reason`+`usage` 해석, 둘 다 아니면 `bad_response`와 `ResponseShape`(키 이름만), 헤더 `cf-ai-neurons`.
  research R-06 과금 분류표의 모든 행(200 해석 성공·실패, 429+3036, 429 그 밖, 5xx, 시간 초과, 연결·읽기 오류, 401, 403, 400+3030, 그 밖의 4xx)을 표 시험으로 고정: 결과 종류·`billable`·측정 Neurons.
  같은 상태 코드·오류 코드에 `rest.py` `classify`와 같은 종류(일시·할당·인증·입력 한도)를 내는지 비교. 예외 문구에 토큰·계정·본문 없음
- [ ] T036 [US6] `src/qello_knowledge/adapters/workers_ai/generation.py`: `GenerationTransport`(urllib, 호출마다 시간 제한, `TimeoutError`·`socket.timeout`·`URLError(reason=timeout)` → 시간 초과, 그 밖 → 일시),
  오류 판정(R-06 표), `WorkersAiGenerationProvider(account_id, api_token, transport=None)`. `rest.py`는 공개 상수만 가져온다. T035 통과
- [ ] T037 [P] [US6] `tests/unit/generation/test_gen_retry_usage.py`(spec FR-020~024, US6, SC-007): 일시 실패 → 재시도 성공(시도 2, 기록 2, 호출 4), 일시 실패 2회 → `generation_failed(transient)`, 시간 초과 → 재시도,
  할당 소진·인증·잘못된 응답 → 재시도 없음, 마감이 모자라면 재시도하지 않음(가짜 `monotonic`), `retry_delay`에 제공자 `retry_after` 전달, Neurons: 헤더 측정 → 토큰 × 단가(추정) → 예상 입력 + 출력 상한(추정),
  과금 안 되는 실패 0, 성공 시도 기록이 후처리 뒤이고 빈 결과면 `outcome='bad_response'`, 출력 잘림(`finish_reason == "length"`, 또는 없음 + 출력 토큰 = 상한) → `flags.truncated`, 기록 실패 → 답 유지·`usage_record_failed`·경고 로그 1줄,
  `usage_today`가 마지막 성공 기록 값, `usage_today.query_reserve_exceeded`면 원문 없는 경고 로그 한 줄을 남기고 생성 결과는 그대로(spec FR-021·US6 3, `embedding/service.py`의 `QUERY_RESERVE_WARNING` 꼴, 독립 검토 M4),
  생성 단계 호출 ≤ 4
- [ ] T038 [P] [US6] `tests/unit/generation/test_gen_input_limit.py`(spec FR-019 (2), SC-009): 검색 요청별 덮어쓰기로 Context 예산·질문 길이를 최대로 올린 입력(계산 36,364 > 32,768)은 호출 없이 `generation_failed(input_too_long)`, 기록 없음
- [ ] T039 [US6] `generation/service.py`: contracts/generation.md 3절 6~8단계 완성(호출 직전 한도, 시도·재시도·마감, 실패 즉시 기록·성공은 후처리 뒤 기록, R-06 Neurons 규칙, 잘림, 기록 실패 처리, 예비분 초과 경고). T037·T038 통과
- [ ] T039a [US6] `tests/unit/generation/test_gen_no_raw_text.py`에 재시도·시간 초과·할당 소진·인증·잘못된 응답·기록 실패·예비분 초과 경고 경로를 더하고 표식 0건을 확인한다(T030의 나머지, 독립 검토 M2)
- [ ] T040 [P] [US6] `tests/localdb/generation/test_gen_usage_ledger.py`(research R-06, data-model 6절): `0006` 적용 뒤 `qk.generation_record`가 행을 넣고 `AnswerUsageToday`(생성·질의 임베딩·질의응답 합계·색인·하루 전체·예비분 초과)를 돌려줌,
  `purpose`는 `'generate'`만 허용, `attempt` 1·2만, `outcome` 7종만, 음수 거부, 원문 열 없음. 질의 임베딩 기록(`qk.embedding_record`)과 생성 기록을 섞은 날 `answer_total`이 둘의 합이고 예비분 초과 판정이 이 합 기준,
  기존 `qk.embedding_usage_today`·`qk-index usage` 값과 색인 예산 판정(`qk.embedding_reserve`)은 생성 기록 전후로 같음, `qk.generation_usage_prune(90)`이 91일 전 행을 `qk.generation_usage_daily`로 합치고 지움, 재실행 안전
- [ ] T041 [US6] `src/qello_knowledge/adapters/postgres/migrations/0006_generation_usage.sql`: data-model 6절 그대로(테이블 2개·함수 3개 추가만, 기존 객체 변경 없음).
  함수 인자: `qk.generation_record(p_run_id text, p_model_id text, p_prompt_version text, p_attempt smallint, p_input_tokens int, p_output_tokens int, p_estimated_input_tokens int, p_neurons numeric, p_measured boolean,
  p_outcome text, p_truncated boolean, p_query_reserve int) returns jsonb`(돌려주는 키는 data-model `AnswerUsageToday` 필드 이름 그대로), `qk.generation_usage_prune(retention_days int default 90) returns jsonb`(키
  `days_rolled_up`·`rows_deleted`, `qk.embedding_usage_prune`과 같음, 독립 검토 L6). `uv run qk-migrate`는 출력의 대상이 `target=local`인지 확인한 뒤 두 번 실행하고 두 번째 `applied=0`(독립 검토 L8)
- [ ] T042 [US6] `src/qello_knowledge/adapters/postgres/generation_usage.py`: `PostgresGenerationLedger(url, query_reserve)`(`record`·`today`·`prune`, `adapters/postgres/usage.py`와 같은 연결·오류 처리). T040 통과
- [ ] T043 [P] [US6] `tests/unit/indexer/test_gen_usage_prune_cli.py`: `qk-index usage prune`이 임베딩 정리 뒤 생성 정리도 부르고 생성 쪽 `days_rolled_up`·`rows_deleted`를 함께 출력, 원격 대상 규칙(`--allow-remote`)은 그대로,
  `qk-index usage`(today) 출력은 바뀌지 않음. 기존 `tests/unit/indexer/test_cli_usage.py`의 prune 시험(65~76행)은 기대 출력에 생성 쪽 줄을 더하고 가짜 생성 장부(`generation_ledger_factory`)를 주입하도록
  고친다. 검사하는 내용(대상 표시, 원격 대상이면 연결 없이 종료 3, `--allow-remote`면 정리)은 그대로 둔다(2026-10-23 사용자 결정, 독립 검토 H1). 생성 정리 출력 줄은 `generation_days_rolled_up=<n> generation_rows_deleted=<n>`
- [ ] T044 [US6] `src/qello_knowledge/indexer/usage.py`·`indexer/cli.py`: `prune` 경로에 생성 장부 정리를 더하고 `main()`·`run_usage`에 생성 장부 팩토리 주입 자리(`generation_ledger_factory`, 기본 `PostgresGenerationLedger`)를 둔다.
  운영 워크플로 `.github/workflows/index-sync.yml:30`의 `qk-index usage prune --allow-remote`가 바뀌지 않고 생성 사용량도 정리해야 한다. T043 통과
- [ ] T045 [P] [US6] `tests/unit/config/test_gen_settings_registry.py`(research R-12): `QK_GEN_MODEL`·`QK_GEN_MAX_TOKENS`·`QK_GEN_TEMPERATURE`·`QK_GEN_TIMEOUT_SECONDS`·`QK_GEN_PROMPT_VERSION`가 질의·색인 진입점에 등록되고
  기본값·범위가 data-model 1절과 같음, `config/check.py`의 `generation_settings(settings) -> GenerationSettings | None`(불러온 설정을 바꾸는 하나뿐인 함수, `budget_settings` 꼴. T034·T048이 쓴다, 독립 검토 L6),
  생성 설정에 문제가 있을 때만 설정 검사 보고에 `CrossCheck`가 생기고 기본 설정이면 `checks`에 생성 항목이 없음(기존 `tests/unit/embedding/test_settings.py:20`·`:37`이 그대로 통과, 독립 검토 H2),
  설정 예시 파일(`.env.example`)이 재생성본과 같음(`tests/unit/config/test_example_file.py` 방식. 재생성은 `uv run python -m qello_knowledge.config.example`, 파일은 직접 읽지 않는다, 독립 검토 L9)
- [ ] T046 [US6] `src/qello_knowledge/config/registry.py`·`config/check.py`·설정 예시 파일: 환경값 5개 등록, `generation_settings`, 문제가 있을 때만 생기는 생성 설정 검사, 예시 재생성. T045와 기존 설정 시험 통과

**Checkpoint**: 제공자·사용량·설정 완료

---

## Phase 9: User Story 7 - 운영 담당자가 명령으로 질문부터 답변까지 확인한다 (P3)

**Goal**: `qk-index ask`(contracts/cli.md).

**Independent Test**: 로컬 DB에 합성 문서를 넣고 가짜 제공자·가짜 임베딩으로 명령을 실행해 출력·종료 코드·비출력 항목을 본다(spec US7).

- [ ] T047 [P] [US7] `tests/unit/indexer/test_gen_ask_cli.py`(contracts/cli.md 1~4절): 질문은 표준 입력만(빈 입력 → 종료 2), 기본 가짜 제공자, `--provider workers-ai`일 때만 실제 제공자 팩토리 호출과 실행 전 표준 오류 알림
  (모델·프롬프트·예상 입력 토큰·예상 Neurons·재시도 최대치, 질문 없음), `--prompt`, 상태별 종료 코드(0 `answered`·`cannot_confirm`, 1 `retrieval_failed`·`outgoing_blocked`·`generation_failed`, 2 설정 검사 실패, 3 원격 대상 + `--allow-remote` 없음),
  사람용·`--json` 출력 꼴, 출처 줄 꼴, 표시 줄, 오늘 사용량 줄(가짜면 "가짜 실행은 기록하지 않음", 생성 호출 0), 응답 꼴 줄, 출력·로그에 질문 원문 없음
- [ ] T048 [US7] `src/qello_knowledge/indexer/ask_cli.py`·`indexer/cli.py`: `add_ask_parser`, `main()`에 `ask_factory` 주입 자리(`search_factory` 꼴, `cli.py:36`·`tests/localdb/retrieval/test_search_command.py:24-33`, 독립 검토 L3),
  `postgres_ask(settings, source, policy, *, embedding_provider=None, generation_provider=None, transport=None)`(`postgres_search` 재사용, 생성 설정은 `generation_settings`,
  `security_outgoing_check(policy)`, `query_retry_delay`, 가짜면 기록 `MemoryLedger`·오늘 사용량은 `PostgresGenerationLedger.today()` 읽기만), `run_ask`. T047 통과
- [ ] T049 [P] [US7] `tests/localdb/generation/test_gen_ask_command.py`: 합성 문서를 넣은 로컬 DB에서 가짜 임베딩 제공자(`FakeEmbeddingProvider`)와 (1) 가짜 생성 제공자로 `answered`·출처 줄, (2) `WorkersAiGenerationProvider` + 가짜 전송으로
  `PostgresGenerationLedger`에 기록 1행·`usage_today` 표시, (3) 활성 인덱스 없음 → `retrieval_failed` 종료 1. 외부 호출 0, 질문 원문이 출력·`qk.generation_usage`에 없음. T048 뒤 통과

**Checkpoint**: 확인 명령 완료

---

## Phase 10: Polish & Cross-Cutting

- [ ] T050 경계·회귀 확인: `uv run pytest tests/unit/test_boundaries.py`, 기존 QK-EMB-001·QK-RET-001·QK-SEC-001·QK-STO-001 시험 전부 통과, `uv run qk-migrate` 두 번(대상 `target=local` 확인, 두 번째 `applied=0`),
  `git diff origin/main --stat -- src/qello_knowledge/adapters/workers_ai/rest.py src/qello_knowledge/retrieval src/qello_knowledge/query/app.py src/qello_knowledge/indexer/search_cli.py src/qello_knowledge/adapters/postgres/migrations/000[1-5]*`가 비어 있음
  (바꾸지 않기로 한 파일, 독립 검토 L11). 실측 질문 세트 `gen-ko-v1`(T034 안 데이터)은 후처리·프롬프트 코드와 다른 커밋으로 넣는다(AGENTS.md 3.4 취지)
- [ ] T051 quickstart.md 1절 전체 실행(`python scripts/preflight.py`, `git diff --check`, `uv run ruff check .`, `uv run ruff format --check .`, `uv run qk-dev db up`, `uv run qk-migrate` × 2, `QK_REQUIRE_LOCALDB=1 uv run pytest`).
  결과를 "실행 기록"에 적고 이 목록 체크 표시를 갱신한다
- [ ] T052 `TASK.md` Decisions·검증 기록 갱신, `/pr-draft-summary`로 PR 초안(CLAUDE.md 의무 사용)

---

## 사람 단계

| 단계 | 내용 | 상태 | 비용·허락 |
| --- | --- | --- | --- |
| H01 | `uv run python specs/QK-GEN-001-answer-generation/measurement/measure_generation.py --provider workers-ai --only 1 --prompt gen-p1 --out <저장소 밖 경로>`로 응답 꼴(`ResponseShape`)을 확인한다. research R-01의 두 꼴 가정과 다르면 어댑터(T036)만 고치고 기록한다 | 구현 뒤 | 생성 1회, 보통 약 7 Neurons(최대 약 58). 사람 확인 뒤 |
| H02 | 같은 스크립트를 `--provider workers-ai --prompt both`로 실행해 SC-008 수치(문항별 상태, 후처리 전 수치, 문장마다 인용 비율, 지연 p50·p95, Neurons)를 기록한다 | H01 뒤 | 24회, 상한 약 920 Neurons(모두 재시도 시 최대 약 1,840). 예상량·최대치 보고 뒤 사람 확인 |
| H03 | H02 답변 원문(저장소 밖 파일)을 사람이 읽고 확인 불가 판정 100%(근거 없음·무관 문항)·지시문 따른 답 0·충돌·현재 상태 문구·FR-009 (나) 발생 횟수를 판정해 "실행 기록"에 남긴다 | H02 뒤 | 없음 |

---

## Dependencies & Execution Order

- Phase 1 → Phase 2 → US1 → US2 → US3 → US4. US5는 US1 뒤 시작할 수 있다(T031~T032는 `render.py`라 US4의 T027 뒤에 한다, T033~T034는 US4 뒤). US6은 US1 뒤 시작할 수 있다(T035·T036·T040~T046은 독립, T037~T039는 `service.py`라 US4의 T028 뒤). US7은 US6 뒤. Polish는 마지막.
- 같은 파일을 고치는 작업은 순서대로 한다: `generation/service.py` T016 → T019 → T020(빈 결과 연결) → T028 → T039, `generation/postprocess.py` T015 → T020 → T023, `generation/render.py` T014 → T027 → T032,
  `test_gen_no_raw_text.py` T030 → T039a. T034의 실제 제공자 경로는 T036 뒤에만 쓰인다.
- 사람 단계 H01은 T036·T034 뒤, H02는 H01 뒤, H03은 H02 뒤.

## Parallel Example

```text
Phase 2: T003, T004, T007, T010 (시험) → T005 → T006, T008, T011 → T009
US1:     T012, T013 (시험) → T014, T015 → T016
US3:     T021, T022 (시험) → T023 → T024
US4:     T025, T026, T029 (시험) → T027 → T028 → T030
US6:     T035, T037, T038, T040, T043, T045 (시험) → T036, T041 → T042, T044, T046 → T039 → T039a
US7:     T047 (시험) → T048 → T049
```

## Implementation Strategy

1. MVP: Phase 1·2 + US1. 여기서 멈춰도 가짜 제공자로 출처 붙은 답을 만들 수 있다.
2. US2~US4로 확인 불가·후처리·보안을 완성한다. 여기까지가 QK-BOT-001이 쓸 생성 경계다.
3. US5로 기준 프롬프트와 실측 스크립트를, US6으로 실제 제공자·사용량·설정을, US7로 확인 명령을 더한다.
4. 스토리마다 시험 → 구현 → 체크포인트 → 커밋(`/harness-commit`).
5. 구현과 자동 검증 뒤 사람 단계 H01~H03(실제 Workers AI 호출, 사람 확인).

## 실행 기록

- 2026-10-23 T007: 승인 원문 고정 파일 `tests/unit/generation/golden/gen-p1-system.txt`(2,184바이트)·`gen-p1-template.txt`(69바이트)는 `TASK.md` "승인된 입력"의 두 코드 블록에서,
  `gen-base-system.txt`는 spike-workers-ai 부록 B "시스템 프롬프트:" 코드 블록에서, `gen-base-template.txt`는 research R-02 코드 블록(들여쓰기 제거)에서 한 번 뽑아 대조했다. 끝 줄바꿈은 넣지 않았다.
  `generation/prompts.py`의 상수는 이 파일에서 만들었다.
- 2026-10-23 환경: 이 PC(Windows, cp949 기본 인코딩)에서는 시험을 `PYTHONUTF8=1`로 돌린다. 기준선(이 작업 전 `tests/unit`)에서 `tests/unit/test_boundaries.py`의 기존 3건
  (`test_violation_is_detected`, `test_chunking_violations_are_detected`, `test_domain_must_not_import_retrieval`)이 Windows 경로 구분자(`\`)로 실패한다(1,253 passed, 3 failed). 이 작업과 무관하고 CI(ubuntu)에서는 통과한다.
  새 경계 시험은 구분자를 `/`로 맞춰 비교한다.
- 2026-10-23 T014·T015·T016: `render.py`(무력화 포함)와 `postprocess.py`(research R-04 1~11단계 전체), `service.py`(contracts 3절 전체)를 US1에서 한 번에 구현했다(QK-RET-001 T028 `pack.py`와 같은 방식).
  US2~US4·US6 시험이 각 단계를 확인하고, 그 작업들은 시험 통과 확인과 빈 곳 보완만 남는다. 골든 렌더링 3종(`golden/render-v1-*.txt`)은 구현 출력을 research R-03 꼴과 눈으로 대조한 뒤 고정했다.
- 2026-10-23 T019·T020: T016 구현이 이미 판정 순서·문장 나누기·(가)(나)(다)·빈 결과를 담고 있어 T017·T018이 코드 변경 없이 통과했다.
- 2026-10-23 T023: T015 구현이 research R-04 1~11단계를 이미 담고 있어 T021·T022·T024가 코드 변경 없이 통과했다(155 passed).
- 2026-10-23 T027·T028: T014·T016 구현이 무력화·판정 순서·묶음 검사를 이미 담고 있어 T025·T026이 코드 변경 없이 통과했다. T030 파일에 T039a의 재시도·기록 실패·예비분 경고 경로도 함께 썼다(T016이 그 경로를 이미 구현). 188 passed.
