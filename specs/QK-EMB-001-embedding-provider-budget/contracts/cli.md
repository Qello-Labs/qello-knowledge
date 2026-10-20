# Contract: CLI

## qk-index usage

오늘(UTC) 임베딩 사용량과 남은 색인 예산을 출력한다. 외부 호출 없음, 저장소 조회만.

```text
qk-index usage [--json]
```

사람용 출력 예(값은 예시):

```text
usage_day=2026-10-20 (UTC, 한국 시간 09:00 기준 초기화)
index: used=312.40 budget=5000 remaining=4687.60
query: used=0.52 reserve=3000
total=312.92 allowance=10000 estimated_share=3%
```

- `--json`이면 `qk.embedding_usage_today` 결과를 그대로 낸다.
- 종료 코드: 0 정상, 1 설정 검사 실패(FR-017 교차 검사 포함), 2 저장소 사용 불가. 인자 형식 오류도 argparse 규칙대로 2로 끝난다.

## qk-index usage prune

```text
qk-index usage prune [--retention-days 90] [--allow-remote]
```

90일 지난 호출별 기록을 일 합계로 옮기고 지운다(FR-025). 출력은 `target=local|remote` 다음 줄에 `days_rolled_up=N rows_deleted=M`.
두 번째 실행은 `0`, `0`이다. 지우는 대상은 사용량 기록뿐이고 청크·벡터는 건드리지 않는다.

- `--retention-days`는 1 이상이다. 0이나 음수는 오늘 기록을 지워 그날 예산을 초기화하므로 거부한다(SQL 함수도 거부한다).
- 대상이 로컬 DB가 아니면 `--allow-remote` 없이는 지우지 않고 종료 코드 3으로 끝낸다(2026-10-20 결정, `qk-migrate`의 파괴 차단과 같은 방식).

## qk-index check (기존 명령에 검사 추가)

설정 검사 보고에 `QK_EMBED_INDEX_BUDGET + QK_EMBED_QUERY_RESERVE ≤ QK_EMBED_DAILY_ALLOWANCE` 교차 검사를 더한다. 어기면 종료 코드 1, 값은 숫자만 출력한다.
