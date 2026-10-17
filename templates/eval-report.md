# Eval Report: <EVAL-ID>

> Warning: 비공개 문서 원문, 민감한 질의 원문, 개인 식별 정보, 토큰, `.env` 값을 복사하지 않는다.
> 집계값, 질문 ID, 논리 라벨, 정리한 요약만 기록한다.

> Created at: `<CREATED-AT>`
> Jira 이슈: `<JIRA-ISSUE-URL>`
> Result: `PASS | FAIL | PARTIAL | NOT_RUN`

## 1. Contract

실행 전에 작성하고, 실행 후에 바꾸지 않는다.

- 가설: 무엇을 바꾸면 어떤 지표가 어떻게 변하는가
- Before: commit, index_version, 설정 요약
- After: commit, index_version, 설정 요약
- Primary metric:
- Guardrail metrics: 답변 충실성, p95 지연, Neurons 사용량 등
- 성공 기준:
- 중단 기준:

## 2. Eval set

- eval_set_version:
- 질문 수:
- 출처: 실제 팀 질문 / 합성 질문 / 혼합(비율)
- 질문 유형 분포: 진행 상태 / 구현 여부 / 용어 / 문서 내용 / 회의 내용 / 기타
- 정답 라벨 기준과 라벨러: 사람 / 모델 / 모델 후 사람 검토(표본 수)
- 이번 실행에서 평가 세트 변경: 아니오 / 예(사유, 별도 커밋)

## 3. Environment

계정, 주소, 토큰은 적지 않는다.

| Item | Before | After |
| --- | --- | --- |
| Embedding model / dimension | | |
| Generation model | | |
| Chunking version | | |
| Retrieval settings (vector k, keyword k, RRF k, 최종 k, 문맥 확장) | | |
| LlamaIndex / pgvector version | | |
| Run location / cache state | | |

## 4. Retrieval results

| Metric | Before | After | n | Notes |
| --- | ---: | ---: | ---: | --- |
| Recall@5 | | | | |
| Precision@5 | | | | |
| MRR | | | | |

질문 유형별 결과:

| Question type | n | Recall@5 Before | Recall@5 After | MRR Before | MRR After |
| --- | ---: | ---: | ---: | ---: | ---: |
| | | | | | |

## 5. Generation results

| Metric | Before | After | n | Grader |
| --- | ---: | ---: | ---: | --- |
| Faithfulness (근거 없는 주장이 없는 답변 비율) | | | | 코드 / 모델 / 사람 |
| Citation validity (인용한 Source가 주장을 담고 있는 비율) | | | | |
| Answer relevance | | | | |
| "확인할 수 없습니다" 응답 비율 | | | | |

모델 채점을 썼다면 채점 모델, 루브릭, 사람이 다시 확인한 표본 수와 일치율을 적는다.

## 6. Cost and latency

| Metric | Before | After |
| --- | ---: | ---: |
| Neurons per question | | |
| Total Neurons / daily free limit | | |
| Retrieval p50 / p95 | | |
| Generation p50 / p95 | | |

## 7. Failure analysis

| Question ID | Failure type | Suspected cause | Follow-up |
| --- | --- | --- | --- |
| | 검색 누락 / 순위 / 문맥 부족 / 환각 / 오래된 정보 / 자료 충돌 | | |

## 8. Interpretation

- 지지하거나 기각한 가설:
- 적용 한계(표본 수, 질문 편향, 캐시 상태):
- 별도 작업이 필요한 후속 결정:

## 9. Verification

- 실행한 명령과 결과:
- 실패하거나 차단된 검사:
- 남은 위험:
