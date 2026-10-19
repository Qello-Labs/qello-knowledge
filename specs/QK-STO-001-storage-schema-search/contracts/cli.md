# Contract: 명령

## `uv run qk-migrate`

마이그레이션 묶음을 `DATABASE_URL`(없으면 로컬 개발 DB 기본값) 대상에 적용한다(FR-016~020, research R-08).

| 옵션 | 뜻 |
| --- | --- |
| (없음) | 아직 성공 기록이 없는 마이그레이션을 번호 순으로 적용 |
| `--dry-run` | 적용할 목록만 출력하고 아무것도 바꾸지 않음 |
| `--allow-destructive` | 로컬이 아닌 대상에 `-- qk:destructive` 마이그레이션 적용을 허용. 사람 확인 뒤에만 쓴다 |

출력(표준 출력, 한 줄씩):

```text
target=local
apply 0001 initial_schema ok
applied=1 skipped=0
```

두 번째 실행:

```text
target=local
applied=0 skipped=1
```

| 종료 코드 | 상황 |
| --- | --- |
| 0 | 모두 적용했거나 적용할 것이 없음 |
| 1 | 마이그레이션 실패. 해당 마이그레이션 변경은 남지 않고 `failed` 기록이 남는다 |
| 2 | 체크섬 불일치. 아무것도 적용하지 않음 |
| 3 | 파괴적 마이그레이션을 로컬이 아닌 대상에 `--allow-destructive` 없이 적용하려 함 |
| 4 | 접속 실패 |

- `target=`은 `local` 또는 `remote`만 쓴다. 호스트·포트·사용자·비밀번호는 출력하지 않는다(AGENTS.md 6절).
- 이 작업에서는 운영 저장소에 실행하지 않는다(TASK.md 제외 범위).

## `uv run qk-dev store bench`

로컬 DB 안 별도 데이터베이스(`qk_bench`)에 합성 데이터를 만들어 SC-005·SC-006을 측정하고, 끝나면 그 데이터베이스를 지운다.
로컬이 아닌 대상이면 거부한다(QK-FND-001 R-06 판단 재사용).

| 옵션 | 기본 |
| --- | --- |
| `--text-bytes` | 1,100,000 (inventory 1.2절 Phase 1 규모) |
| `--repeat` | 100 |
| `--top-n` | 20 |

출력: 데이터 규모(청크 수, 원문 바이트), 벡터·키워드 각각 p50·p95(ms), 인덱스 사용 여부, `usage`(전체 바이트, 청크 수, 벡터 수),
원문 대비 저장 배율. 측정 조건(이미지 태그, CPU 아키텍처, 반복 횟수)을 첫 줄에 함께 찍는다.
