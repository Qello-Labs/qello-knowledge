# Contract: `qk-index ask`

질문 하나를 표준 입력으로 받아 검색(QK-RET-001 `retrieve`, 하이브리드)과 생성(`generate`)을 이어 실행한다(spec FR-027, research R-10).

## 1. 인자

| 인자 | 기본 | 설명 |
| --- | --- | --- |
| `--provider {fake,workers-ai}` | `fake` | `workers-ai`일 때만 외부 생성 호출. 질의 임베딩은 `search`와 같이 Workers AI를 쓴다 |
| `--prompt {gen-p1,gen-base}` | 설정값(`gen-p1`) | 프롬프트 버전 |
| `--candidates`, `--budget`, `--expand-top`, `--source-kind`, `--query-rule` | `search`와 같음 | 검색 조건 |
| `--allow-remote` | 없음 | 원격 저장소 대상 실행 허용(`search`와 같은 규칙) |
| `--sources`, `--exceptions`, `--env-file` | `search`와 같음 | |
| `--json` | 없음 | JSON 출력 |
질문은 명령행 인자로 받지 않는다. 표준 입력이 비면 종료 코드 2.

## 2. 실행 전 알림

`--provider workers-ai`면 생성 호출 전에 표준 오류로 한 줄을 낸다: 모델, 프롬프트 버전, 예상 입력 토큰, 예상 Neurons(예상 입력 × 입력 단가 + `max_tokens` × 출력 단가), 재시도 시 최대치.
대화형 확인은 하지 않는다(사람이 명시적으로 고른 실행이다). 질문 원문은 내지 않는다.

## 3. 출력

사람용(기본):

```text
대상: local | 제공자: fake | 프롬프트: gen-p1-<hash> | 상태: answered
답변:
<후처리한 답변 본문>
출처:
[S1] <제목> — <원본 링크> (버전 <짧은 버전>, 수정 2026-10-10, 수집 2026-10-21)
표시: 출처 확인 안 됨 / 출력 잘림 / 사용량 기록 실패 (해당할 때만)
요약: 묶음 3/4(뺀 1: S2 aws-access-key) · 입력 1,234(예상 1,100) · 출력 87 · 6.4 Neurons(측정) · 시도 1 · 1,050 ms · 호출 6(생성 2)
오늘 사용량: 생성 120.5 · 질의 임베딩 3.1 · 질의응답 합계 123.6 / 예비분 3,000 · 하루 전체 455.0 (qk-index usage의 query_used는 질의 임베딩만 센다)
  가짜 제공자 실행이면 이 줄은 DB의 오늘 값을 읽기만 해서 보여 주고 "가짜 실행은 기록하지 않음"을 붙인다. 생성 호출 수는 0으로 센다.
응답 꼴: choices · usage 있음 · Neurons 헤더 있음 · 종료 사유 있음
후처리: 지운 인용 0 · 인식 못 한 꼴 0 · 인용 없는 문장 1 · 지운 URL 0 · 지운 출처 줄 0 · 무력화 0
검색: <qk-index search 요약 한 줄과 같음>
```

`--json`은 `{"target", "provider", "result": {"status", "answer", "citations": [...], "summary": {...}, "retrieval": {...}}}`. `summary`·`retrieval`에는 질문·본문이 없다.

## 4. 종료 코드

| 코드 | 경우 |
| --- | --- |
| 0 | `answered`, `cannot_confirm` |
| 1 | `retrieval_failed`, `outgoing_blocked`, `generation_failed` |
| 2 | 인자·설정 오류(빈 표준 입력, 설정 검사 실패) |
| 3 | 원격 대상인데 `--allow-remote` 없음 |

## 5. 조립

`indexer/ask_cli.py`의 `postgres_ask(...)`가 `postgres_search`(`indexer/search_cli.py`)의 저장소·임베딩 조립을 재사용하고, `WorkersAiGenerationProvider` 또는 가짜 제공자,
`PostgresGenerationLedger`(가짜 제공자면 기록은 `MemoryLedger`, 오늘 사용량 표시는 `PostgresGenerationLedger.today()` 읽기만), `security_outgoing_check(policy)`, `query_retry_delay`(`indexer/search_cli.py:41`)를 넣는다. 가짜 제공자 실행은 운영 사용량을 기록하지
않는다(가짜 실행이 그날 합계를 바꾸지 않게). 시험은 `provider`·`transport`·`embedding_provider` 주입 자리로 가짜 전송과 가짜 임베딩 제공자를 넣어 `PostgresGenerationLedger`까지 돌린다(research R-10).
질의 임베딩은 `--provider`와 관계없이 `search`와 같은 실제 제공자를 쓴다(기본 `ask`도 질의 임베딩 1회, 1 Neurons 미만).
