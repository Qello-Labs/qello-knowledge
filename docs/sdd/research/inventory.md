# 자료 인벤토리

WBS 0.2 산출물이다. 색인할 자료원이 어디에 어떤 형태로 있는지 정리한다. 수치는 아래 조사 시점의 기본 브랜치 기준이고, 자료가 바뀌면 다시 잰다.

| 항목 | 내용 |
| --- | --- |
| 조사일 | 2026-10-06 |
| 조사 방법 | `gh` CLI로 GitHub API 조회(저장소 메타데이터, 언어, 기본 브랜치 트리, 검색 API, Projects). 파일 크기는 Git blob 크기다 |
| 기준 커밋 | `dnd-15th-2-backend@c070ae0`, `dnd-15th-2-android@6a12cbd` |
| 진행 상태 | GitHub 저장소·DB·OpenAPI 조사 완료. ClickUp, 회의록, Figma는 미조사 |

## 1. GitHub 저장소

### 1.1 저장소 목록

Qello 제품 저장소는 `Qello-Labs` 조직이 아니라 DND 동아리 조직(`dnd-side-project`)에 있다. `Qello-Labs`에는 이 저장소만 있다.

| 저장소 | 공개 범위 | 기본 브랜치 | 언어(바이트) | 저장소 크기 | 파일 수 | 브랜치 | PR / Issue / Release | 생성 | 색인 대상 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `dnd-side-project/dnd-15th-2-backend` | 공개 | `main` | Java 4,613,002 · Python 338,074 · HCL 128,651 · PLpgSQL 99,917 · Shell 16,053 · 기타 2,913 | 5,832 KB | 1,569 | 142 | 146 / 169 / 0 | 2026-07-23 | 대상 |
| `dnd-side-project/dnd-15th-2-android` | 공개 | `main` | Kotlin 412,576 | 2,304 KB | 299 | 2 | 19 / 21 / 0 | 2026-07-28 | 대상 |
| `Qello-Labs/qello-knowledge` | 비공개 | `main` | Python 76,501 · PowerShell 64,641 · Shell 342 | 164 KB | — | 3 | — | 2026-10-04 | 대상 아님(이 시스템 자체) |

- 저장소 크기는 GitHub `diskUsage`(이력 포함)이고, 파일 수는 기본 브랜치 트리의 파일 수다.
- 두 제품 저장소 모두 Release와 태그가 없다.
- 백엔드는 Java 21, Spring Boot 3.5, PostgreSQL(PostGIS)이다. Android는 Kotlin 단일 언어이고 네트워크는 Ktor 3.5.1, 로컬 저장은 Room을 쓴다.

### 1.2 백엔드 저장소 구성

| 분류 | 경로 | 파일 | 크기 | 쓰는 단계·명세 | 색인 제안 |
| --- | --- | --- | --- | --- | --- |
| 루트 문서 | `README.md`, `AGENTS.md`, `CLAUDE.md`, `CODEX.md`, `TASK.md` | 5 | 44 KB | Phase 1 | 포함 |
| ADR | `docs/adr/` | 10 | 68 KB | Phase 1 | 포함 |
| 제품 설계·데이터 모델 | `docs/product/`(인증·알림·온보딩·답변 신고 설계, 백엔드 로드맵, ERD 설명, `schema-manifest.md`) | 7 | 223 KB | Phase 1 | 포함 |
| API 규약 | `docs/api-response.md`, `docs/error-codes.md`, `docs/filtering-production-gate.md`, `docs/push-production-setup.md`, `docs/api/OPENAPI_WRITING_GUIDE.md` | 5 | 64 KB | Phase 1 | 포함 |
| 하네스 | `docs/harness/` | 15 | 58 KB | Phase 1 | 포함 |
| 계획·명세 | `docs/superpowers/plans/`(18), `docs/superpowers/specs/`(11) | 29 | 599 KB | Phase 1 | 포함 |
| 인프라 문서 | `infra/**/*.md` | 5 | 14 KB | Phase 1 | 포함 |
| 기타 문서 | 디렉터리별 `AGENTS.md`, PR 템플릿, `scripts/repo-map/README.md` | 5 | 13 KB | Phase 1 | 포함 |
| 테스트 계획·결과 | `docs/test-plans/`(68), `docs/test-reports/`(4), `docs/reports/tests/`(62) | 134 | 2,015 KB | Phase 1~2 | 결정 필요 |
| 설계 보고서 | `docs/reports/`(인프라 설계 보고서 7개 포함, 테스트 제외) | 16 | 421 KB | Phase 1~2 | 결정 필요 |
| 에이전트 설정 | `.claude/`, `.agents/`, `.codex/`, `agents/`, `templates/` | 75 | 195 KB | — | 결정 필요 |
| 실험 기록 | `docs/experiments/codex-agents/`(md 31, csv 13, json 12) | 56 | 1,329 KB | — | 제외 |
| Java 코드 | `src/main/java/` | 738 | 1,756 KB | Phase 2 QK-CHK-001 | 포함 |
| Java 테스트 | `src/test/java/`(195), `src/integrationTest/java/`(113) | 308 | 2,841 KB | Phase 2 QK-CHK-001 | 포함 |
| Flyway 마이그레이션 | `src/main/resources/db/migration/` `V1`~`V30` | 31 | 169 KB | Phase 4 QK-ING-007 | 포함 |
| DBML | `docs/product/data-model/direction_communication.dbml` | 1 | 139 KB | Phase 4 QK-ING-007 | 결정 필요 |
| OpenAPI | `docs/api/openapi.json` | 1 | 323 KB | Phase 4 QK-ING-006 | 포함 |
| Terraform | `infra/`(`bootstrap`, `environments/dev/{storage,test-server}`, `modules/{app-server,network,s3-private-bucket}`) | 33 | 135 KB | Phase 4 QK-ING-009 | 포함(`.terraform.lock.hcl` 제외) |
| GitHub 템플릿 | `.github/ISSUE_TEMPLATE/`(Issue Form 6종), `.github/PULL_REQUEST_TEMPLATE.md` | 8 | — | Phase 3 QK-ING-005 | 템플릿 필드 추출에 사용 |
| 스크립트 | `scripts/`(Python 17개, 실험 스크립트 포함) | 24 | — | — | 제외 |

- 마크다운은 모두 330개, 3,978 KB다. "포함"으로 표시한 Phase 1 문서는 81개, 1,083 KB다. "결정 필요" 문서까지 모두 넣으면 약 3.7 MB가 된다.
- 바이트 수는 임베딩 사용량을 대략 비교하는 용도다. 토큰 수와 Neurons 추정은 Workers AI 확인(0.6)에서 입력 한도와 단가를 확인한 뒤 계산한다.
- 비밀값 검사(QK-SEC-001)를 꼭 거쳐야 하는 파일: `.env.example`, `infra/**/terraform.tfvars.example`(3개), `agents/model-profiles.example.yml`, `src/main/resources/application*.yml`(5개), `src/integrationTest/resources/application-*.yml`(2개).

### 1.3 Android 저장소 구성

| 분류 | 경로 | Kotlin 파일 | 크기 | 쓰는 단계·명세 | 색인 제안 |
| --- | --- | --- | --- | --- | --- |
| 화면 | `presentation/` | 109(+테스트 2) | 332 KB | Phase 2 QK-CHK-001 | 포함 |
| 데이터(`remote/` 하위 파일 37개 포함) | `data/` | 52(+테스트 2) | 56 KB | Phase 2, Phase 4 QK-CHK-004 | 포함 |
| 도메인 | `domain/` | 32 | 12 KB | Phase 2 | 포함 |
| 앱 진입점 | `app/` | 1(+테스트 2) | 1 KB | Phase 2 | 포함 |
| 빌드 설정 | `build-logic/`, `*.gradle.kts`, `gradle/libs.versions.toml` | 11 | 9 KB | — | 제외 |
| 문서 | `README.md`(19바이트), Issue·PR 템플릿 | md 4 | 1 KB | — | 템플릿만 사용 |
| 리소스 | XML 38, 이미지 16, 폰트 3 | — | — | — | 제외 |

- Android 저장소에는 설계 문서가 거의 없다. Android 관련 질문은 코드와 백엔드 문서, ClickUp에서 답을 찾아야 한다.

### 1.4 저장소 밖의 GitHub 자료

| 자료 | 위치 | 규모 | 비고 |
| --- | --- | --- | --- |
| GitHub Project `Qello Backend Roadmap` | `dnd-side-project` 조직 Project #141 | 항목 153 | 백엔드 README는 이 Project의 draft item을 개발 백로그 기준으로 둔다 |
| GitHub Project `Qello Backend 진행 현황 (완료 작업)` | `dnd-side-project` 조직 Project #144 | 항목 14 | 진행 현황 질문(Phase 3)의 자료원 후보 |
| API 문서 사이트 | `deploy-api-docs` 워크플로가 `docs/api/openapi.json`을 GitHub Pages(`https://dnd-side-project.github.io/dnd-15th-2-backend/`)에 배포 | — | 공개 페이지 |

## 2. OpenAPI 노출 위치

- 원본은 백엔드 저장소의 `docs/api/openapi.json`이다(커밋된 파일). 같은 파일이 GitHub Pages로 배포된다.
- 수집기(QK-ING-006)는 저장소 파일을 읽으면 된다. 실행 중인 서버의 문서 엔드포인트를 호출할 필요가 없다.

## 3. DB 접근 가능 여부

### 3.1 현재 구성

| 항목 | 내용 |
| --- | --- |
| DB 종류 | PostgreSQL 16 + PostGIS 3.5 컨테이너(`postgis/postgis:16-3.5-alpine`) |
| 위치 | dev 테스트 서버(EC2 `t3.small`) 한 대에서 Docker Compose로 백엔드 컨테이너와 함께 실행. RDS가 아니다 |
| 데이터 | 별도 EBS 볼륨. 테스트 계정과 테스트 데이터만 쓴다 |
| 네트워크 | 보안 그룹은 앱 포트 하나만 연다. DB 컨테이너는 호스트 포트를 열지 않는다. SSH 포트도 닫혀 있고 SSM Session Manager로만 접속한다 |
| 가동 시간 | EventBridge Scheduler가 매일 새벽 3시에 서버를 정지한다. 자동 시작은 없다(수동 시작) |
| 스키마 관리 | Flyway(`src/main/resources/db/migration`, `V1`~`V30`) |
| 근거 | 백엔드 저장소 `infra/modules/app-server/main.tf`, `infra/modules/app-server/user_data.sh.tftpl`, `infra/environments/dev/test-server/README.md` |

### 3.2 실제 DB에 연결할 수 있는가

기술적으로는 가능하다. 경로는 SSM 포트 포워딩으로 서버에 터널을 연 뒤 Docker 내부 네트워크의 DB 컨테이너에 붙거나, SSM 명령으로 서버 안에서 `pg_dump --schema-only`를 실행하는 방식이다. 다만 MVP에서는 권하지 않는다.

| 이유 | 설명 |
| --- | --- |
| 서버가 대부분 꺼져 있다 | 매일 새벽 정지되고 수동으로만 켠다. 정해진 주기로 수집하면 대부분 실패한다 |
| 인프라 변경이 필요하다 | RAG 수집기에 SSM 세션 권한(IAM)과 DB 읽기 전용 계정을 새로 줘야 한다. 백엔드 저장소의 인프라 승인 절차를 거쳐야 한다 |
| 얻는 정보가 거의 같다 | 스키마는 Flyway 마이그레이션을 순서대로 적용한 결과다. 저장소의 마이그레이션 파일과 `docs/product/data-model/`의 ERD 설명, `schema-manifest.md`로 같은 정보를 얻는다 |
| 행 데이터는 색인 대상이 아니다 | 테스트 데이터라도 사용자 정보 형태를 띤다. AGENTS.md 3.1에 따라 색인하지 않는다 |
| 비밀값이 늘어난다 | DB 계정 정보와 AWS 자격 증명을 RAG 서버가 들고 있어야 한다 |

**제안**: DB 스키마는 Flyway 마이그레이션과 `docs/product/data-model/` 문서를 기준으로 수집한다. 실제 DB 연결은 하지 않고, 0.5의 "(선택) DB 읽기 전용 계정"은 발급하지 않는다. "dev 서버에 어느 마이그레이션까지 적용됐나" 같은 현재 상태 질문이 실제로 반복되면 Phase 6 후보(6.2 AWS 현재 상태 조회)에서 다시 검토한다.

## 4. ClickUp Space·Folder 구조

미조사.

## 5. 회의록 위치·형식

미조사.

## 6. Figma 파일 목록·소유자·좌석

미조사.

## 7. 로드맵과 다른 점·결정할 것

| 번호 | 발견한 점 | 영향 | 필요한 결정 |
| --- | --- | --- | --- |
| F-1 | 제품 저장소가 `dnd-side-project` 조직에 있고 공개 저장소다 | 0.5 GitHub 토큰은 이 조직의 공개 저장소 읽기 권한이면 된다. 조직 관리자 승인이 필요한지 확인한다 | 토큰 발급 대상 조직 |
| F-2 | Android 네트워크 계층은 Retrofit이 아니라 Ktor다 | QK-CHK-004("API ↔ 컨트롤러 ↔ Retrofit") 교차 관계 추출 대상을 Ktor 호출 코드로 바꿔야 한다 | 로드맵·명세 표현 수정 |
| F-3 | 백엔드 개발 백로그와 진행 현황이 GitHub Projects에 있다 | Phase 3 진행 현황 자료원이 ClickUp Tasks만이 아닐 수 있다 | 진행 현황의 기준 자료원(ClickUp Tasks, GitHub Projects, 또는 둘 다) |
| F-4 | Release와 태그가 없다 | QK-ING-005의 Release 수집은 지금 수집할 자료가 없다 | QK-ING-005 범위에서 Release를 뺄지 |
| F-5 | 백엔드 README의 "현재 단계"가 오래됐다(마이그레이션·인프라가 아직 없다고 적혀 있지만 이미 있다) | RISK-06(오래된 원본 문서)이 실제로 있다 | 원본 정리 여부(백엔드 팀) |
| F-6 | 테스트 계획·결과 문서가 134개, 2 MB로 Phase 1 대상 문서(1.1 MB)보다 크다 | 색인 범위에 따라 문서 임베딩 사용량이 3배 넘게 달라진다 | 1.2절 "결정 필요" 항목의 포함 여부 |
| F-7 | DB는 꺼져 있는 시간이 긴 dev 서버 컨테이너다 | 실제 DB 연결 수집은 맞지 않는다 | 3.2절 제안 채택 여부 |
