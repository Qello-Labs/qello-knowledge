# Contract: `qk-index search`와 `qk-dev eval-index prepare`

**명세**: [../spec.md](../spec.md) FR-025, FR-029 · **결정**: [../research.md](../research.md) R-09·R-10

기존 하위 명령은 바꾸지 않는다.

## 1. `qk-index search`

질문은 표준 입력에서 읽는다(끝까지, UTF-8). 명령행 인자로 받지 않는다.

| 옵션 | 기본 | 뜻 |
| --- | --- | --- |
| `--mode {hybrid,vector,keyword}` | `hybrid` | 검색 방식 |
| `--query-rule {kw-query-v1,kw-query-raw}` | `kw-query-v1` | 질의 쪽 규칙 |
| `--candidates N`, `--budget N`, `--expand-top N` | 설정값 | 요청 단위 덮어쓰기(범위 검사) |
| `--ranks-only` | 꺼짐 | 문맥 확장·담기 생략(FR-023) |
| `--source-kind K`(반복) | 없음 | 필터 |
| `--allow-remote` | 꺼짐 | 로컬이 아닌 저장소 허용. 사용량 기록이 원격에 쓰인다 |
| `--sources`, `--exceptions` | `config/sources.toml`, `config/security_exceptions.toml` | 전송 검사 정책 로딩(`load_policy`는 자료원 설정이 필요하다) |
| `--json`, `--env-file` | 꺼짐, `.env` | 다른 명령과 같음 |

출력(사람용): 첫 줄 `target=local|remote mode=… index_version=… index_rule=… query_rule=…`, 통합 순위 표(순위, 점수, 벡터 순위, 키워드 순위, 출처 링크, 제목 경로),
Context 요약(묶음 수, 사용 토큰/예산, 건너뛴 청크 수와 사유), 생략한 검색과 사유, 외부 호출 수, 임베딩 Neurons, 자료원별 원본 리비전.
전송 직전 검사는 색인과 같은 `load_policy`(`--exceptions`, 기본 `config/security_exceptions.toml`)로 정책을 만들고 출처 없이 부른다(출처별 예외는 적용되지 않는다). 질문·검색어·본문은 출력하지 않는다.

| 종료 코드 | 뜻 |
| --- | --- |
| 0 | `ok` 또는 `no_results`(축소 동작 포함) |
| 1 | 실패 종류(data-model 2.7) |
| 2 | 인자·설정 오류(argparse 포함) |
| 3 | 원격 대상인데 `--allow-remote` 없음 |

## 2. `qk-dev eval-index prepare`

| 옵션 | 뜻 |
| --- | --- |
| `--rule {kw-index-baseline-v1,kw-index-idsplit-v1}` | 색인 쪽 규칙(필수) |
| `--commit SHA` | 40자 커밋 SHA(필수). 짧은 SHA·브랜치 이름은 거부 |
| `--source NAME` | 기본 `dnd-backend-docs` |
| `--from-url-env VAR` | 임베딩 캐시 원본 접속 정보가 든 환경 변수 이름. 기본 `DATABASE_URL` |
| `--allow-embed` | 캐시로 처리되지 않는 임베딩이 있을 때 실행 허용. 없으면 예상 Neurons를 보이고 멈춤 |
| `--json`, `--env-file` | 다른 명령과 같음 |

대상은 언제나 로컬 컨테이너이고, 접속 정보는 컨테이너 주소와 준비용 이름으로 만든다(`DATABASE_URL`을 쓰지 않음). 원본은 읽기 전용 트랜잭션으로만 읽는다.
자료원 설정과 범위 검토 파일은 임시 사본에서만 `ref`를 바꾼다. 순서와 재실행 규칙은 research R-09.

| 종료 코드 | 뜻 |
| --- | --- |
| 0 | 준비·활성화 완료 |
| 1 | 단계 실패(어느 단계인지 출력) |
| 2 | 인자 오류 |
| 4 | 예상 Neurons가 0이 아닌데 `--allow-embed` 없음 |
| 5 | 최종 이름 데이터베이스가 이미 있음(준비용 `__preparing` 잔여물은 다시 만들고 멈추지 않음) |

완성된 평가용 데이터베이스(최종 이름) 정리는 사람이 `DROP DATABASE`로 한다. 이 명령이 지우는 것은 로컬 컨테이너의 `qk_eval_*__preparing` 잔여물뿐이다(AGENTS.md 4절, research R-09).
