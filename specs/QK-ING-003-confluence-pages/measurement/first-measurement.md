# QK-ING-003 첫 실제 수집 측정 (H03, FR-027·SC-010)

> 측정일: 2026-11-09 (UTC `06:57`)
>
> 명령: `uv run qk-dev source measure --name confluence-scrum --chunk --json --env-file <로컬 .env>`
>
> 실행: QK-ING-003 마무리 세션(#72). 사용자 승인("측정 실행 승인", 조건: `GET`만, 약 322요청, Workers AI 0 Neurons)

이 기록에는 집계 값만 둔다. 페이지는 ID로만 가리키고 제목·제목 경로·링크·본문·사람 이름은 적지 않는다(FR-027, SC-004).

## 조건

| 항목 | 값 |
| --- | --- |
| 자료원 | `confluence-scrum`(`enabled = false`. 측정은 비활성 자료원도 잰다, contracts/cli.md) |
| 범위 | `space_key = "SCRUM"`, `space_id = "98307"`, `judge_mode = "site_users"`, `exclude_trees = ["3571713"]`, 대응표 12개 |
| 확인 기록 | `config/source_reviews/confluence-scrum.toml`(2026-11-05, 사이트 사용자 3명 확인) |
| 보안 규칙 버전 | `sec-17dc0f4ddea7` |
| 청킹 규칙 버전 | `chk-md-20d966f730bb` |
| 예상 Neurons 기준 모델 | `@cf/baai/bge-m3`(1,075 Neurons / 100만 토큰) |
| 인덱스 버전 | 바뀌지 않음(`iv-4c0bc4fcc642`). 저장·임베딩 없음 |
| 실행 환경 | macOS 15.3.1 arm64 / Python 3.13.15 |
| 실행 한도 | 분당 60요청, 실행당 2,000요청, 대기 300초, 실행 1,800초, 페이지 1,000,000바이트 |

## 결과

| 항목 | 값 |
| --- | --- |
| Atlassian 요청 | 308건(예상 약 322건 안). 모두 `GET`, 모두 `200` |
| 소요 시간 | 306.3초 |
| 목록 완전성 | 완전(`listing_complete = true`, 멈춤 없음) |
| 페이지 수 | 160 |
| 본문 조회 | 146 |
| 본문 총 바이트 | 3,617,155 |
| 가장 큰 페이지 | 163,200바이트(페이지 상한 1,000,000 안) |
| 조회 실패 | 0 |
| 미분류 | 1 |
| 예상 Neurons(캐시 전 상한) | 약 763.2. 하루 색인 예산 5,000의 약 15% |
| Workers AI 실제 호출 | 0건(0 Neurons) |

### 엔드포인트별 요청

| 엔드포인트 | 상태 | 건수 |
| --- | --- | --- |
| `GET /spaces` | 200 | 1 |
| `GET /spaces/{id}/pages` | 200 | 1 |
| `GET /pages/{id}/restriction-state` | 200 | 160 |
| `GET /pages/{id}?body` | 200 | 146 |

폴더가 0개라 폴더 엔드포인트는 부르지 않았다.

### 판정별 페이지 수

| 판정 | 페이지 | 규칙별 |
| --- | --- | --- |
| `PASSED` | 145 | `confluence-access-v1` 145 |
| `PATH_EXCLUDED` | 14 | `not-indexed-type` 11, `excluded-tree` 1, `space-home` 1, `unclassified` 1 |
| `SECRET_BLOCKED` | 1 | `assigned-secret` 1 |

- `SECRET_BLOCKED`: 페이지 `98694`, 본문 742행·783행, 접근 범위 `TEAM`. 이 페이지는 색인과 임베딩에서 빠진다. 원본에 실제 비밀값이 있는지는 사람이 확인한다(이 기록과 측정 출력에는 값이 없다).
- `excluded-tree` 1건은 골든셋 v0 질문 목록(`3571713`)이다. 검색 평가가 오염되지 않는다.

### 변환 경고

| 종류 | 건수 |
| --- | --- |
| `UNSUPPORTED_BLOCK` | 2,175 |
| `MEETING_METADATA_MISSING` | 6 |

### 청킹(`--chunk`)

| 항목 | 값 |
| --- | --- |
| 청킹한 본문 | 114 |
| 빈 본문 | 31 |
| 청크 수 | 2,346 |
| 청킹 실패 | 0 |

## 확인한 것

- **H02 토큰 범위**: `read:space:confluence`(`/spaces`), `read:page:confluence`(`/pages`·`restriction-state`) 요청이 모두 `200`이라 두 범위는 포함돼 있다.
  `read:folder:confluence`는 스페이스에 폴더가 0개라 이 측정으로는 확인하지 못했다. 폴더가 생기기 전에는 영향이 없다.
- **비용(SC-010)**: 예상 Neurons 약 763이 하루 색인 예산 5,000보다 작아, 켜기 전에 따로 보고할 초과는 없다.
- **요청 한도**: 308건은 실행당 2,000건 안이고, 1,800초 안에 끝났다.

## 켜기 전에 볼 것(이 기록의 판단 아님)

- `UNSUPPORTED_BLOCK` 2,175건: 지원하지 않는 블록이 많다. 종류별 내역은 측정 출력에 없어 어느 블록이 빠지는지 따로 확인해야 검색 품질 영향을 알 수 있다.
- `MEETING_METADATA_MISSING` 6건: 회의록 메타데이터(날짜 등)가 없는 회의록이 있다.
- 빈 본문 31건: 대부분 하위 페이지만 묶는 분류 페이지로 보이지만 페이지별로 확인하지 않았다.
- 페이지 `98694`의 비밀값 탐지가 실제 값인지, 원본에서 지워야 하는지.
