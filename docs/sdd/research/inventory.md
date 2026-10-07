# 자료 인벤토리

WBS 0.2 산출물이다. 색인할 자료원이 어디에 어떤 형태로 있는지 정리한다. GitHub 수치는 조사 시점의 기본 브랜치 기준이고, ClickUp은 조사일에 화면에 보인 항목 기준이다. 자료가 바뀌면 다시 잰다.

| 항목 | 내용 |
| --- | --- |
| 조사일 | GitHub·OpenAPI·DB 2026-10-06, ClickUp·회의록 2026-10-07 |
| 조사 방법 | GitHub: `gh` CLI로 GitHub API 조회(저장소 메타데이터, 언어, 기본 브랜치 트리, 검색 API, Projects). 파일 크기는 Git blob 크기다. ClickUp: 로그인된 웹 화면에서 조회했다. API와 토큰은 쓰지 않았다 |
| 기준 커밋 | `dnd-15th-2-backend@c070ae0`, `dnd-15th-2-android@6a12cbd`. ClickUp은 커밋이 없어 조사일 기준이다 |
| 진행 상태 | GitHub 저장소·DB·OpenAPI·ClickUp·회의록 조사 완료. Figma는 MVP 제외 결정으로 조사 보류(6절) |

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

### 4.1 구조

조사 대상은 `김도연's Workspace`의 `Qello` Space다([Qello Space](https://app.clickup.com/1100370000016776/v/o/s/1100370000057600)). 업무는 Folder·List의 Task로, 문서는 `Team Docs` Doc의 하위 페이지로 관리한다.

```text
Qello [Space]
├─ Android 스프린트 [Folder]
│  ├─ Android [List]
│  ├─ Sprint 1 (28/9 - 4/10) [Sprint List]
│  └─ Sprint 2 (5/10 - 11/10) [Sprint List]
├─ Backend 스프린트 [Folder]
│  ├─ Backend [List]
│  ├─ Sprint 1 (28/9 - 4/10) [Sprint List]
│  └─ Sprint 2 (5/10 - 11/10) [Sprint List]
├─ Bug Tracking [List]
├─ 팀 일정 [List]
├─ 팀 전체 스프린트 [Board View]
└─ Team Docs [Doc, Verified wiki]
   ├─ 회의록
   ├─ ADR
   ├─ Design Docs
   ├─ API Docs
   ├─ 설계 문서
   ├─ 개발 규칙 문서
   ├─ 기타문서
   ├─ Qello 기능명세서
   └─ 관리자용
```

### 4.2 자료 종류와 색인 제안

| 위치 | 형태 | 내용 | 쓰는 단계·명세 | 색인 제안 |
| --- | --- | --- | --- | --- |
| `Team Docs` 하위(회의록·관리자용 제외) | Doc 페이지 | ADR, 디자인, API, 설계, 개발 규칙, 기능명세서, 기타 | Phase 2 QK-ING-003 | 포함 |
| `Team Docs` → `회의록` | Doc 페이지 | 5절 | Phase 2 QK-ING-003 | 포함 |
| `Team Docs` → `관리자용` | Doc 페이지 | 내용 미확인 | — | 권한 확인 전 제외 |
| Folder별 `Android`·`Backend` List, Sprint List 4개 | Task | 파트별 백로그와 스프린트 | Phase 3 QK-ING-004 | 포함 |
| `Bug Tracking` | Task | 버그 | Phase 3 QK-ING-004 | 포함 |
| `팀 일정` | Task | 정기 회의 일정, 스프린트 설정 안내 | Phase 3 QK-ING-004 | 포함 |

- List별 Task 수와 Team Docs 하위 페이지의 수·크기는 세지 않았다. 0.5에서 ClickUp 토큰을 받은 뒤 API로 다시 잰다.
- 화면 조회라서 보관(archived)된 항목이나 조사한 계정에 권한이 없는 항목은 빠졌을 수 있다.

## 5. 회의록 위치·형식

### 5.1 위치

경로는 `Qello` → `Team Docs` → `회의록` → 회의 페이지다([회의록 목록](https://app.clickup.com/1100370000016776/v/dc/z8rzdfhxc8-98/z8rzdfhxc8-38)). 회의록은 ClickUp Tasks가 아니라 Docs 페이지다. 회의 일정은 따로 `팀 일정` List의 Task로 관리한다([팀 일정](https://app.clickup.com/1100370000016776/v/l/z8rzdfhxc8-1058)).

| 구분 | 저장 방식 | 회의 페이지 | 수 |
| --- | --- | --- | --- |
| 1주차 | `1주차 회의` 아래 중첩 | `1주차 아이디어 회의 1일차`~`4일차` | 4 |
| 2주차 | `2주차 회의` 아래 중첩 | `2주차 회의 1일차`~`3일차` | 3 |
| 3주차 | `3주차 회의` 아래 중첩 | `3주차 회의 1일차`~`4일차` | 4 |
| 4주차 | `4주차 회의` 아래 중첩 | `4주차 회의 1일차`~`3일차` | 3 |
| 5~8주차 | `회의록` 바로 아래 | 각 `N주차 회의 1일차` | 4 |
| 12·13주차 | `회의록` 바로 아래 | 각 `N주차 회의` | 2 |

- 회의 페이지는 20개다. 주차 상위 페이지 4개와 본문이 빈 `Untitled` 페이지 1개는 세지 않았다.
- 목록에 9~11주차가 없다. 다른 위치에 있는지는 확인하지 않았다.

### 5.2 형식

본문을 열어 본 문서는 `4주차 회의 1일차`(일시 2026-07-28)와 `13주차 회의`(일시 2026-09-23) 두 개이고, 형식이 같았다. 나머지 18개는 열지 않았다.

본문 위에 다음 필드가 있다.

| 필드 | 내용 |
| --- | --- |
| 사람 | 참석자 목록 |
| 생성일, 수정일 | 원문에 적힌 일시 |
| 숫자 | 숫자 값. 용도 미확인 |
| 일시 | 회의 날짜 |
| 장소/채널 | 두 문서 모두 `디스코드` |

- 필드 이름(특히 `숫자`)으로 보아 Notion 데이터베이스 속성이 이전 과정에서 본문에 남은 것으로 추정한다. 0.3에서 확인한다.
- 제목에는 날짜가 없다. 회의 날짜 메타데이터는 `일시` 필드에서 읽어야 한다.

본문은 다음 다섯 절로 되어 있다.

1. `📚 회의 아젠다`: 번호 목록으로 안건을 적는다.
2. `🗒️ 회의 내용`: 안건별 소제목 아래 논의 내용과 후속 작업을 적는다.
3. `🌟 다음 회의까지 준비할 내용`: 다음 회의 일정, 준비 사항, 담당자를 적는다. 13주차 문서는 `백엔드`·`안드로이드`·`디자인`으로 나눈다.
4. `🌟 다음 회의에 진행할 내용`: 다음 회의 안건을 적는다.
5. `🎸 기타`: 추가 기록, 사진, 원본 링크를 적는다.

- 이 형식이 ClickUp에 등록된 공식 템플릿인지는 확인하지 않았다. 회의록 템플릿은 0.4에서 확정한다.

## 6. Figma 파일 목록·소유자·좌석

조사 보류. 팀 회의에서 MVP 자료원에서 Figma를 빼기로 결정했다(2026-10-07 사용자 확인). 로드맵에서도 Figma 수집(QK-ING-008)은 MVP(Phase 2) 이후인 Phase 4 작업이므로, Phase 4 명세를 쓰기 전에 조사한다.

다시 조사할 때 확인할 것:

- 팀·프로젝트별 파일 목록과 파일별 소유자. 떠난 디자이너가 소유한 파일이 있는지 본다(RISK-03).
- 좌석 수와 종류. View·Collab 좌석은 파일 본문 조회가 월 단위로 제한된다(RISK-03).
- 조사 방법은 Figma 화면 확인을 기본으로 한다. Figma MCP는 파일 URL 단위로 읽고 팀 파일 목록과 좌석은 조회하지 못하는 것으로 보여(인증 전 판단) 파일별 페이지·프레임 수를 셀 때만 보조로 쓴다.

## 7. 로드맵과 다른 점·결정할 것

| 번호 | 발견한 점 | 영향 | 필요한 결정 |
| --- | --- | --- | --- |
| F-1 | 제품 저장소가 `dnd-side-project` 조직에 있고 공개 저장소다 | 0.5 GitHub 토큰은 이 조직의 공개 저장소 읽기 권한이면 된다. 조직 관리자 승인이 필요한지 확인한다 | 토큰 발급 대상 조직 |
| F-2 | Android 네트워크 계층은 Retrofit이 아니라 Ktor다 | QK-CHK-004("API ↔ 컨트롤러 ↔ Retrofit") 교차 관계 추출 대상을 Ktor 호출 코드로 바꿔야 한다 | 로드맵·명세 표현 수정 |
| F-3 | 백엔드 개발 백로그와 진행 현황이 GitHub Projects에 있다 | Phase 3 진행 현황 자료원이 ClickUp Tasks만이 아닐 수 있다. ClickUp에도 파트별 Sprint List가 있어(4절) 두 곳의 상태가 다를 수 있다 | 진행 현황의 기준 자료원(ClickUp Tasks, GitHub Projects, 또는 둘 다) |
| F-4 | Release와 태그가 없다 | QK-ING-005의 Release 수집은 지금 수집할 자료가 없다 | QK-ING-005 범위에서 Release를 뺄지 |
| F-5 | 백엔드 README의 "현재 단계"가 오래됐다(마이그레이션·인프라가 아직 없다고 적혀 있지만 이미 있다) | RISK-06(오래된 원본 문서)이 실제로 있다 | 원본 정리 여부(백엔드 팀) |
| F-6 | 테스트 계획·결과 문서가 134개, 2 MB로 Phase 1 대상 문서(1.1 MB)보다 크다 | 색인 범위에 따라 문서 임베딩 사용량이 3배 넘게 달라진다 | 1.2절 "결정 필요" 항목의 포함 여부 |
| F-7 | DB는 꺼져 있는 시간이 긴 dev 서버 컨테이너다 | 실제 DB 연결 수집은 맞지 않는다 | 3.2절 제안 채택 여부 |
| F-8 | ClickUp Workspace 이름이 팀원 개인 이름(`김도연's Workspace`)이다 | 0.5 ClickUp 수집 전용 계정을 이 Workspace에 초대해야 한다. 소유자·관리자, 요금제, 멤버 한도는 확인하지 않았다 | 수집 계정 초대 주체와 요금제 확인 |
| F-9 | Team Docs에 ADR, API Docs, 설계 문서가 있다 | 백엔드 저장소 `docs/adr/`, `docs/api/`와 내용이 겹치면 같은 주제가 두 번 색인되고 서로 다른 답이 나올 수 있다 | 주제별 기준 원본(ClickUp 또는 GitHub) |
| F-10 | Team Docs에 `관리자용` 페이지가 있다 | 권한 범위를 확인하지 못하면 AGENTS.md 3.1에 따라 검색 결과에 노출할 수 없다 | 색인 포함 여부, `access_scope` 판별 방법(0.3) |
| F-11 | 회의록 중첩 방식과 제목 규칙이 섞여 있다. 4주차까지는 주차 페이지 아래 일차별 페이지, 5주차부터는 `회의록` 바로 아래 페이지다. 제목도 `N주차 회의`, `N주차 회의 N일차`, `N주차 아이디어 회의 N일차`로 다르다 | 제목이나 계층으로 회의 날짜·주차를 판별하면 틀린다. 본문의 `일시` 필드를 기준으로 삼아야 한다 | 0.4 폴더 구조·회의록 템플릿 확정 때 반영 |
| F-12 | 회의록 목록에 9~11주차가 없고, 본문이 빈 `Untitled` 페이지가 있다 | 해당 기간 질문에는 근거가 없다. 빈 페이지는 수집에서 걸러야 한다 | 9~11주차 회의록 존재 여부(팀 확인), `Untitled` 정리(원본 정리는 팀이 한다) |
| F-13 | 확인한 회의록 두 개에 Notion 원본 링크가 있고, `4주차 회의 1일차`의 일부 이미지는 `Notion 원본에서 확인`이라는 대체 문구로 남아 있다 | Notion→ClickUp 이전 손실(RISK-01)이 실제로 있다. 답변 근거가 Notion 링크로 이어질 수 있다 | 0.3에서 손실 범위 확인, Notion을 자료원에 남길지 |
| F-14 | 팀 회의에서 MVP에서 Figma를 제외하기로 했다(2026-10-07 사용자 확인) | Phase 0의 0.2 Figma 조사와 0.5 Figma 토큰 발급이 지금은 필요 없다. 로드맵 0.2·0.5 표에는 아직 Figma가 남아 있다 | 로드맵 0.2·0.5의 Figma 항목을 Phase 4 준비 작업으로 옮길지 |
