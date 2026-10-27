# Eval Report: gh68-budget-3000

> Warning: 비공개 문서 원문, 민감한 질의 원문, 개인 식별 정보, 토큰, `.env` 값을 복사하지 않는다.
> 집계값, 질문 ID, 논리 라벨, 정리한 요약만 기록한다.

> Created at: `2026-10-27`
> Jira 이슈: 해당 없음(Jira 없이 진행하는 예외 작업, GitHub Issue #68)
> Result: `PASS`(사람 판정, 아래 5절)

## 1. Contract

실행 전에 사용자와 합의한 내용(2026-10-27)을 실행 뒤 이 양식으로 옮겼다.

- 가설: 문맥 예산을 2,000에서 3,000으로 올리면 Q05의 근거 절(ADR-0008 `고려한 선택지`)이 문맥에 들어가 근거 문서를 인용해 답하고, 다른 질문은 나빠지지 않는다.
- Before: 질의 릴리스와 같은 코드 `3a5a98e`, 인덱스 `iv-4c0bc4fcc642`, `--budget 2000`(현재 기본값)
- After: 같은 코드·인덱스, `--budget 3000`(이 변경의 기본값과 같은 동작)
- Primary metric: 질문 세트 판정 기준(SC-002)의 통과 수
- Guardrail metrics: 없음 질문의 표준 확인 불가 유지, 질문당 생성 Neurons
- 성공 기준: Q05 통과, 다른 10문항 회귀 없음
- 중단 기준: 당일 질의 예비분(3,000) 초과 예상

## 2. Eval set

- eval_set_version: `qk-bot-001-h05` v1([`h05-question-set.md`](h05-question-set.md))
- 질문 수: 11(있음 8, 없음 3). SC-005 합성 비밀값 질문 S01은 생성 경로가 아니어서 뺐다
- 출처: 합성 질문(팀 공용 백엔드 문서 기준)
- 질문 유형 분포: 문서 내용 8, 자료 없음 3
- 정답 라벨 기준과 라벨러: 사람(2026-10-27 확정). 판정도 사람이 한다
- 이번 실행에서 평가 세트 변경: 아니오

## 3. Environment

| Item | Before | After |
| --- | --- | --- |
| Embedding model / dimension | 활성 인덱스 `iv-4c0bc4fcc642`와 같음 | 같음 |
| Generation model | `@cf/qwen/qwen3-30b-a3b-fp8`, 프롬프트 `gen-p1` | 같음 |
| Chunking version | 활성 인덱스와 같음 | 같음 |
| Retrieval settings | 하이브리드, 후보 20, RRF k 60, 상위 확장 8, 앞뒤 1, 예산 2,000 | 예산 3,000, 나머지 같음 |
| Run location / cache state | 운영 인스턴스의 동기화 체크아웃(`qk-index ask --provider workers-ai --allow-remote`), 질문마다 1회 | 같음 |

## 4. Retrieval results

순위 지표(Recall@5, MRR)는 재지 않았다. 예산은 순위를 바꾸지 않고 문맥에 담기는 범위만 바꾼다.
Q05의 문맥 구성만 따로 확인했다: 예산 2,000은 사용 1,980, 6위 중심 `고려한 선택지`가 `budget_exhausted`. 예산 3,000은 사용 2,972, ADR-0008 묶음에 `고려한 선택지`·`선택 이유`가 함께 담겼다.

## 5. Generation results

| 질문 | 유형 | Before(2,000) 출처 | After(3,000) 출처 | Before 판정 | After 판정 |
| --- | --- | --- | --- | --- | --- |
| Q01 | 있음 | ADR-0002 | ADR-0002 | 통과 | 통과 |
| Q02 | 있음 | `api-response.md`, ADR-0005 | `api-response.md` | 통과 | 통과(사람 판정, 아래) |
| Q03 | 있음 | ADR-0006 | ADR-0006 | 통과 | 통과 |
| Q04 | 있음 | ADR-0007 | `ONBOARDING_COUNTRY_DESIGN.md`, `AUTH_DESIGN.md` | 통과 | 통과(사람 판정, 아래) |
| Q05 | 있음 | 없음(`unsupported_answer`, "명시되지 않음") | ADR-0008 | 실패 | 통과 |
| Q06 | 있음 | `error-codes.md` | `error-codes.md` | 통과 | 통과 |
| Q07 | 있음 | ADR-0004 | ADR-0004 | 통과 | 통과 |
| Q08 | 있음 | `SECRET_HANDLING.md` | `SECRET_HANDLING.md` | 통과 | 통과 |
| Q09 | 없음 | 표준 확인 불가 | 표준 확인 불가 | 통과 | 통과 |
| Q10 | 없음 | 표준 확인 불가 | 표준 확인 불가 | 통과 | 통과 |
| Q11 | 없음 | 표준 확인 불가 | 표준 확인 불가 | 통과 | 통과 |

| Metric | Before | After | n | Grader |
| --- | ---: | ---: | ---: | --- |
| 판정 기준 통과(SC-002, 사람 판정) | 10/11 | 11/11 | 11 | 사람 |
| 판정 기준 글자 그대로(근거 문서가 출처에 있음) | 10/11 | 9/11 | 11 | 코드 |
| 출처 확인 안 됨 표시 | 1 | 0 | 11 | 코드 |
| "확인할 수 없습니다" 응답(없음 3문항) | 3/3 | 3/3 | 3 | 코드 |

- Q02·Q04(After): 라벨의 근거 문서(ADR-0005, ADR-0007)가 출처에 없고, 같은 내용을 담은 다른 팀 문서를 인용했다. 답 내용은 핵심 사실과 맞는다.
  판정 기준을 글자 그대로 적용하면 실패지만, 2026-10-27 사용자가 통과로 판정했다. 라벨이 근거 문서를 하나만 두는 한계는 질문 세트 v2 후속으로 남긴다.
- Q05(Before)는 H05 실측·재현에서도 같은 질문이 근거 없이 답하거나 확인 불가로 답했다(예산 2,000에서 3회 모두 실패, 3,000에서 2회 모두 통과).

## 6. Cost and latency

| Metric | Before | After |
| --- | ---: | ---: |
| Neurons per question(생성, 평균) | 15.91 | 19.93 |
| 예상 입력 토큰(평균) | 2,917 | 3,736 |
| Total Neurons / daily free limit | 174.99 / 10,000 | 219.25 / 10,000 |
| Retrieval p50 / p95 | 재지 않음 | 재지 않음 |
| Generation p50 / p95 | 재지 않음 | 재지 않음 |

이 작업의 재현·평가 합계는 431.11 Neurons(생성 430.56, 질의 임베딩 0.55, 측정)다. 질의 예비분 3,000 안이었다.

## 7. Failure analysis

| Question ID | Failure type | Suspected cause | Follow-up |
| --- | --- | --- | --- |
| Q05(Before) | 문맥 부족 | 예산 2,000을 상위 순위의 다른 문서가 먼저 써서 핵심어가 있는 6위 절이 빠졌다 | 이 변경(ADR-025) |
| Q02·Q04(After) | 인용 문서가 라벨과 다름 | 문맥에 같은 내용을 담은 다른 문서가 더 들어갔다 | 질문 세트 v2에서 근거 문서 여러 개 허용 검토 |

## 8. Interpretation

- 지지하거나 기각한 가설: 지지. Q05가 근거 문서를 인용해 답했고 내용 회귀는 없었다.
- 적용 한계: 질문마다 1회 표본이라 모델 출력 편차를 분리하지 못한다. 질문 11개는 한 자료원(백엔드 문서)뿐이다. 지연은 재지 않았다.
- 별도 작업이 필요한 후속 결정: 질문 세트 v2(근거 문서 여러 개), 하루 질의 사용량이 늘 때 담기 규칙 변경 재검토(ADR-025 Revisit conditions).

## 9. Verification

- 실행한 명령과 결과: Bastion 세션(확인 뒤 삭제)에서 `qksync` 환경으로 `qk-index ask --provider workers-ai --budget {2000,3000} --allow-remote --json`을 질문마다 1회, 22건 모두 성공.
- 실패하거나 차단된 검사: 없음.
- 남은 위험: 병합 뒤 질의 서비스에 반영하려면 질의 릴리스 갱신(또는 `query.env`에 `QK_RETRIEVAL_CONTEXT_BUDGET=3000`)이 필요하다. 운영 반영은 따로 승인받는다.
