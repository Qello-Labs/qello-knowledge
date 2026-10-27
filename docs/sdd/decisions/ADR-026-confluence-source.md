# Decision Record: ADR-026 Confluence 자료원 — 팀 스페이스 페이지

> Created at: `2026-10-27`
> Jira 이슈: `https://tkv123.atlassian.net/browse/SCRUM-119`
> 기능명세서 ID: `QK-ING-003`
> Status: Proposed

## Context

팀은 2026-10-17에 작업 관리를 ClickUp에서 Jira `SCRUM` 프로젝트로, 문서를 Confluence `SCRUM` 스페이스로 옮겼다(`docs/github-workflow.md:5`).
로드맵 2.3 QK-ING-003은 ClickUp Docs 수집을 전제로 썼고, AGENTS.md 3.1의 색인 대상 목록에도 ClickUp Docs·Tasks가 있다.
이관 뒤 ClickUp에는 더 이상 새 문서가 쌓이지 않으므로, Phase 2 문서 자료원은 Confluence가 된다.

AGENTS.md 3.1은 새 자료원을 더할 때 데이터 처리 정책을 확인하고 결정 기록을 남기라고 하고, 자료원마다 원본 권한을 메타데이터로 보존하라고 한다.
QK-SEC-001 FR-015는 자료원 종류마다 접근 판정 규칙을 등록하고, 규칙이 없는 종류는 "미확인"으로 막는다. 그래서 Confluence 종류(`confluence_pages`, 가칭)를 추가하려면
이 기록과 QK-ING-003 명세가 함께 필요하다(`src/qello_knowledge/sources/kinds.py`의 "종류 추가는 결정 기록이 필요하다").

Jira 이슈 수집(QK-ING-004, WBS 3.1)은 Phase 3 작업이라 이 기록에 넣지 않는다. 같은 Atlassian 계정·토큰을 쓸 수 있으므로 계정 결정은 Jira에도 맞게 정한다.

## Decision

Confluence Cloud `SCRUM` 스페이스(전역 스페이스, `type=global`, `status=current`)의 현재 페이지(`status=current`)를 새 자료원 종류로 추가하고,
QK-ING-003 구현 뒤 비활성으로 등록했다가 개인 정보 확인 기록이 승인된 뒤 켠다. 수집은 읽기 범위만 고른 범위 지정 API 토큰을 쓰는 수집 전용 계정(서비스 계정 우선)으로 하고,
본문은 ADF(`atlas_doc_format`)로 받아 Markdown으로 바꾼다. 개인 스페이스와 보기 제한이 걸린 페이지는 색인하지 않는다.

| 항목 | 값 |
| --- | --- |
| 자료원 이름(가칭) | `confluence-scrum` |
| 종류(가칭) | `confluence_pages` |
| 범위 | 자료원 하나에 스페이스 하나(`SCRUM`). 원본 정체성은 스페이스 ID다. 개인 스페이스는 키를 적어도 거부한다. 스페이스를 더하는 일은 자료원별 식별 명세 뒤에 한다 |
| 대상 콘텐츠 | 페이지 본문. 첨부 파일, 댓글, 블로그 글, 화이트보드, 데이터베이스는 첫 활성화에서 제외 |
| 호출 | Confluence REST API v2 `GET` 요청만. 쓰기 범위는 고르지 않는다(AGENTS.md 3.1 읽기 전용 소비자) |

## Rationale

### 수집 계정과 토큰

- Atlassian은 범위를 고른 API 토큰("Create API token with scopes")을 지원한다. 만료는 1~365일로 정하고 기본값은 1년이다.
  범위 지정 토큰은 사이트 주소가 아니라 `https://api.atlassian.com/ex/confluence/{cloudId}` 게이트웨이로 호출해야 한다 [A1].
- 범위는 API 작업 종류(보기·쓰기·삭제)를 정할 뿐, 읽을 수 있는 스페이스를 줄이지 않는다. v2 `GET /spaces`·`GET /pages`는 "Only … the user has permission to view" 자료만
  돌려준다 [A3]. 그래서 수집 범위는 토큰이 아니라 수집 계정의 스페이스 권한으로 제한한다(추론, RISK-02).
- 서비스 계정은 조직에 5개까지 무료이고, 토큰을 만드는 절차에 범위 선택 단계가 있으며 만든 뒤에는 범위를 바꿀 수 없다. 범위 없이 만들 수 있는지는 문서에 없다(미확인). Atlassian Administration의
  Directory > Service accounts에서 만든다 [A2]. 사람 좌석을 쓰는지는 문서에서 확인하지 못했다(미확인).
- 고를 범위(최소, granular). v2 OpenAPI의 각 엔드포인트 `x-atlassian-oauth2-scopes` 값에서 가져왔다 [A3].

  | 용도 | 엔드포인트 | 범위 |
  | --- | --- | --- |
  | 스페이스 목록·종류 | `GET /wiki/api/v2/spaces` | `read:space:confluence` |
  | 스페이스 권한 | `GET /wiki/api/v2/spaces/{id}/permissions` | `read:space:confluence` |
  | 페이지 목록·본문 | `GET /wiki/api/v2/spaces/{id}/pages`, `GET /wiki/api/v2/pages/{id}` | `read:page:confluence` |
  | 상위 페이지 | `GET /wiki/api/v2/pages/{id}/ancestors` | `read:content.metadata:confluence` |
  | 보기 제한 상태 | `GET /wiki/api/v2/pages/{id}/restriction-state`(`OPEN`·`EDIT_RESTRICTED`·`VIEW_RESTRICTED`) | `read:page:confluence` |
  | 페이지 직접 권한 | `GET /wiki/api/v2/pages/{id}/permissions` | `read:page:confluence` |

  두 엔드포인트는 페이지 자신의 직접 제한·권한만 준다고 설명돼 있어, 상속 제한은 상위 페이지마다 다시 본다. `restriction-state`가 상속 제한도 반영하는지는 plan에서 재생 응답으로 확인한다.
  v1 `GET /wiki/rest/api/content/{id}/restriction/byOperation`(classic `read:confluence-content.all`)은 v2로 부족할 때의 대안이다 [A4].
  (2026-10-27 독립 검토 M7: 초안의 "v2에 대응 엔드포인트가 없다"는 틀렸다.)
- 비밀값 검사: `secret_rules.py`의 `atlassian-token` 규칙과 `sources/config.py:16`의 `ATATT` 접두어는 기존 Atlassian API 토큰 형식이다.
  지원 문서는 토큰 길이가 일정하지 않다고만 하고 접두어를 밝히지 않는다 [A1]. 범위 지정·서비스 계정 토큰이 같은 접두어인지는 발급할 때 사람이 접두어만 확인한다.
  다르면 비밀값 규칙에 더하는 일을 QK-ING-003 범위에 넣는다.
- 보관: 서버 `/etc/qello-knowledge/sync.env`와 로컬 `.env`에만 둔다. 변수 이름 초안은 `ATLASSIAN_API_TOKEN`, `ATLASSIAN_EMAIL`(기본 인증에 쓰는 계정 메일),
  `ATLASSIAN_CLOUD_ID`다. 계정 메일은 계정 정보라 저장소와 기록에 적지 않는다(AGENTS.md 6절). 교체·유출 대응은 `tokens.md` 6절 형식으로 더한다.

### 원본 권한을 `access_scope`로 옮기는 규칙

QK-SEC-001 FR-016대로, 아래 조건을 모두 만족할 때만 "팀 공용"이고 하나라도 확인하지 못하면 "미확인"이다. 보기 제한이 확인된 페이지는 "제한"이다.

| 순서 | 확인 | 팀 공용 조건 | 아니면 |
| --- | --- | --- | --- |
| 1 | 스페이스 종류(`GET /spaces?type=`) | `global` | `personal`·`collaboration`·`knowledge_base`·`system`·`onboarding`·`xflow_sample_space` 등 → 미확인. 설정에 개인 스페이스 키가 있으면 설정 오류 |
| 2 | 스페이스 상태 | `current` | `archived`·`trashed` → 그 스페이스의 페이지는 모두 미확인(보안 내림) |
| 3 | 스페이스 권한 할당(`GET /spaces/{id}/permissions`) | 설정에 적은 "팀 전체" 그룹이 `operation.key=read`, `targetType=space`를 가진다 | 팀 그룹 할당이 없으면 미확인. 팀 그룹 할당을 읽는 데 필요한 값이 모르는 값이면 미확인. 다른 사용자·역할 할당이 더 있는 것은 판정에 영향 없음 |
| 4 | 페이지와 모든 상위 페이지의 보기 제한(`restriction-state`) | 모두 `VIEW_RESTRICTED`가 아니다 | 제한이 있으면 제한. 조회 실패는 미확인 |
| 5 | 페이지 상태 | `current` | 초안·보관·휴지통은 수집하지 않음 |

- 보기 제한은 하위 페이지로 상속되고, 하위 페이지는 상위보다 넓게 열릴 수 없다 [A6]. 그래서 페이지 자신의 제한만 보면 부족하고 상위 페이지를 모두 본다.
  상위 페이지가 지워지면 하위 페이지의 상속 제한이 풀린다는 Atlassian 버그 보고가 있다 [A7]. 판정은 매 동기화마다 다시 하므로 그 시점의 상태를 따른다(추론).
- `AccessInfo.raw`에 남길 원값: `judge_mode`(team_group/site_users), `space_type`, `space_status`, `team_group_read`(true/false), `site_review_valid`(true/false),
  `read_restricted`(none/self/ancestor), `ancestor_count`. 사용자·그룹 ID는 남기지 않는다.
- 수집 계정이 볼 수 없게 된 페이지는 목록에서 빠질 뿐 "제한"으로 보이지 않는다(목록은 볼 수 있는 페이지만 준다 [A3]). 그래서 지난 실행에 있었는데 목록에서 빠진 페이지는
  단건으로 다시 조회해, 접근 거부·없음이면 보안 내림으로 내린다(QK-ING-003 FR-030, 2026-10-27 사용자 결정).
- 권한 조회가 목록의 10%를 넘는 페이지에서 실패하면(토큰 범위 누락 등) 그 실행을 불완전으로 두고 대량 보안 내림을 하지 않는다(QK-ING-003 FR-031).
- Free 플랜: Confluence Free는 공간 권한·페이지 제한을 바꿀 수 없고 로그인한 사용자 모두에게 열려 있다(기존 설정은 남는다) [A8]. 사이트가 Free면 3·4단계의
  조회 결과가 어떻게 나오는지 plan 단계에서 실측한다. Free면 3단계 대신 "사이트 사용자가 모두 팀원임"을 사람이 확인한 기록을 쓴다.
  기록이 있으면 1·2·4·5단계를 만족하는 페이지를 팀 공용으로 판정하고, 없거나 확인일에서 90일이 지났으면 미확인이다. 사이트 사용자 구성이 바뀌면 기록을 다시 쓴다.
  판정 방식과 기록 해시는 보안 규칙 버전 재료에 넣는다(2026-10-27 사용자 결정, QK-ING-003 FR-012).
- 페이지마다 상위·제한 조회가 붙어 호출 수가 페이지 수의 약 3배다. 상위 페이지 ID별로 판정을 기억하면 줄일 수 있다. 정확한 수는 plan 측정으로 정한다.

### 본문을 Markdown으로 바꾸는 방식

- v2 목록 엔드포인트(`GET /spaces/{id}/pages`)의 `body-format`은 `storage`·`atlas_doc_format` 두 값이고, 단건(`GET /pages/{id}`)은 여기에 `view`·`export_view`·
  `anonymous_export_view`·`styled_view`·`editor`를 더한다. Markdown 형식은 없다 [A3].
- ADF(`atlas_doc_format`)로 받아 이 저장소의 변환기로 Markdown을 만든다.
  - Jira REST API v3의 설명·댓글도 ADF라서 QK-ING-004가 같은 변환기를 쓸 수 있다(추론).
  - 노드 종류가 정해진 JSON이라 HTML 파싱보다 결정적이다.
  - 목록 응답에 본문을 함께 받을 수 있어 페이지별 단건 호출이 필요 없다.
- 변환 규칙(초안. QK-ING-003 명세에서 확정):
  - 제목·문단·목록·표·코드 블록·인용·링크는 Markdown 대응으로 바꾼다.
  - 패널·확장(`expand`)은 제목 줄과 본문으로 펼친다.
  - 모르는 확장(`extension`, `bodiedExtension`, 매크로)은 `[매크로: <키>]` 자리 표시와 수집기 변환 경고를 남긴다(QK-ING-003 FR-015). 청커의 구조 경고(QK-CHK-002 FR-024)와는 따로 센다.
  - 멘션은 표시 이름만 남기고 계정 ID는 버린다(AGENTS.md 3.1 계정 정보). 회의록 참석자·담당자 이름은 색인한다.
    개인 정보 확인 기록에 이름 색인 허용을 적어야 한다(2026-10-27 사용자 결정, QK-ING-003 FR-017·FR-021).
  - 이미지·첨부는 `[이미지]`·`[첨부: 파일 이름]`만 남기고 받지 않는다.
- 변환 결과는 QK-CHK-002 Markdown 청커에 그대로 넘긴다(FR-026). 위치 정보는 페이지 ID와 제목 경로를 쓰고, 블록 단위 위치가 필요한지는 명세에서 정한다.
- 변환 규칙을 바꾸면 같은 원문에서 다른 Markdown이 나오므로, 변환 규칙 버전을 변경 키나 청킹 규칙 버전에 넣는다(AGENTS.md 3.3). 어느 쪽에 넣을지는 plan에서 정한다.

## Alternatives considered

| Alternative | Advantages | Disadvantages | Reason not selected |
| --- | --- | --- | --- |
| 본문을 `storage`(XHTML)로 받아 HTML→Markdown 변환 | 일반 HTML 변환 라이브러리를 쓸 수 있다 | `ac:`·`ri:` 네임스페이스 매크로를 따로 풀어야 하고, Jira v3의 ADF와 변환기가 둘로 갈린다 | 변환기를 하나로 두려고 |
| 단건 `export_view`(렌더링된 HTML)로 받기 | 매크로가 화면과 같은 HTML로 풀린다 | 페이지마다 단건 호출이 필요하고, 렌더링 결과가 Confluence 표시 방식 변경에 따라 바뀐다 | 호출 수와 결정성 |
| 팀원 개인 계정의 범위 지정 토큰 | 발급이 바로 된다 | 그 사람의 개인 스페이스와 제한 페이지까지 보인다. 떠나면 수집이 멈춘다(`tokens.md` T-04와 같은 문제) | RISK-02 |
| 범위 없는 기존 API 토큰 | 사이트 주소로 바로 호출한다 | 계정의 모든 API 권한을 가진다(쓰기 포함) | 읽기 전용 원칙(AGENTS.md 3.1) |
| 사람이 확인한 페이지 허용 목록(0.3 조사 4.3절 제안) | 권한 판정이 단순하다 | 페이지가 늘 때마다 사람이 목록을 고쳐야 한다 | 원본 권한으로 판정할 수 있어서. 원본 권한을 읽지 못하면 이 방식으로 돌아간다 |
| ClickUp Docs를 그대로 수집 | 0.3·0.4 조사가 있다 | 이관 뒤 갱신되지 않는다 | 원본이 바뀌었다 |

## Evidence

- [A1] Atlassian Support, "Manage API tokens for your Atlassian account": https://support.atlassian.com/atlassian-account/docs/manage-api-tokens-for-your-atlassian-account/ (조회 2026-10-27, 페이지에 갱신일 없음)
- [A2] Atlassian Support, "Manage API tokens for service accounts": https://support.atlassian.com/user-management/docs/manage-api-tokens-for-service-accounts/ (조회 2026-10-27)
- [A3] Confluence Cloud REST API v2 OpenAPI: https://dac-static.atlassian.com/cloud/confluence/openapi-v2.v3.json (조회 2026-10-27). `/pages`, `/pages/{id}`, `/spaces`, `/spaces/{id}/pages`,
  `/spaces/{id}/permissions`, `/pages/{id}/ancestors`의 `body-format`·`type`·`status` 값, 권한 설명, 범위. `SpacePermissionAssignment` 스키마(`principal.type` user·group·role, `operation.key`).
- [A4] Confluence Cloud REST API v1 OpenAPI: https://dac-static.atlassian.com/cloud/confluence/swagger.v3.json (조회 2026-10-27). `/wiki/rest/api/content/{id}/restriction/byOperation` 범위.
- [A5] Confluence Cloud "Rate limiting": https://developer.atlassian.com/cloud/confluence/rate-limiting/ (조회 2026-10-27). 포인트 기반 시간당 한도는 2026-03-02부터 Forge·Connect·OAuth 2.0(3LO) 앱에 적용되고,
  API 토큰 기본 인증 호출은 기존 순간 한도를 따른다. 429에는 `Retry-After`가 온다. 범위 지정 토큰의 게이트웨이 호출이 어느 쪽인지는 문서에서 확인하지 못했다(미확인).
- [A6] Atlassian Support, "Add or Remove Page Restrictions": https://confluence.atlassian.com/confcloud/page-restrictions-724764891.html (조회 2026-10-27. 검색 결과 요약으로 확인, 본문 직접 열람 안 함). 보기 제한 상속.
- [A7] CONFCLOUD-26297: https://jira.atlassian.com/browse/CONFCLOUD-26297 (조회 2026-10-27. 검색 결과 요약). 상위 페이지 삭제 시 상속 제한이 풀리는 문제. 해결 여부 미확인.
- [A8] Atlassian Support, "Adjust permissions before downgrading to Confluence Free": https://support.atlassian.com/confluence-cloud/docs/manage-permissions-in-the-free-edition-of-confluence-cloud/ (조회 2026-10-27. 검색 결과 요약).
- Workers AI 학습 미사용·보존: ADR-019 Evidence(Cloudflare "Data usage", 조회 2026-10-20). 저장소 정책: ADR-008 "데이터 처리 정책" 절.
- 이관 사실: `docs/github-workflow.md:5`. Confluence `Qello 마이그레이션 검증 기록`은 이 세션에서 열지 못했다(Atlassian MCP 미인증).

## Data and cost

- 외부로 전송되는 데이터와 제공자의 학습 사용·보존 정책:
  - 수집: Atlassian API 게이트웨이에 `GET` 요청만 보낸다. 보내는 것은 토큰과 요청 경로이고, 받는 것은 팀 스페이스 페이지와 권한 정보다.
    Atlassian은 이 시스템에서 원본 자료원이고 새 외부 모델이 아니다. 우리가 보내는 요청에 콘텐츠가 들어가지 않으므로 학습·보존 정책 확인 대상이 아니다(추론).
  - 임베딩: QK-SEC-001을 통과한 청크 본문을 Workers AI(`@cf/baai/bge-m3`, ADR-002)로 보낸다. 학습 미사용, 동기 추론의 입력·출력 미보관은 ADR-019 Evidence와 같다.
    호출 경로(동기 REST, AI Gateway 없음)가 같으므로 새로 확인할 것은 없다. 경로가 바뀌면 다시 확인한다.
  - 저장: 청크 본문과 메타데이터는 운영 PostgreSQL(OCI 자체 운영, ADR-008)에 저장한다.
  - GitHub 공개 저장소와 달리 Confluence 페이지는 공개 자료가 아니다. 회의록에 참석자 이름, 개인 일정, 외부 연락처가 들어 있을 수 있다.
    그래서 활성화 전에 `config/source_reviews/confluence-scrum.toml` 개인 정보 확인 기록을 쓴다(ADR-019와 같은 절차). 범위를 넓히면 다시 쓴다.
    회의록 참석자·담당자 이름과 멘션 표시 이름은 색인하므로(2026-10-27 사용자 결정) 이 기록에 이름 색인 허용을 적는다. 이름은 청크 본문에 들어가 Workers AI 임베딩 입력으로 간다.
  - 원본에서 페이지가 지워지거나, 보기 제한이 걸리거나, 개인 스페이스로 옮겨지면 다음 동기화에서 검색에서 내린다(QK-SEC-001 FR-018, QK-SYN-001). 원본 보존 기간은 Atlassian 설정을 따르고 이 시스템이 따로 늘리지 않는다.
- 무료 한도와 예상 사용량: 페이지 수·크기를 아직 재지 않았다(미확인). QK-ING-003 plan에서 읽기 전용으로 잰다. ADR-019의 비율(1,083 KB → 약 325 Neurons, 보정 전)을 쓰면 1 MB당 약 300 Neurons이고,
  QK-CHK-001 보정 계수를 적용한 실측 방식(ADR-023)으로 다시 계산한다. 첫 색인이 하루 색인 예산(5,000 Neurons)을 넘으면 스페이스나 페이지 트리를 나눠 켠다.
  Atlassian 요청 수는 페이지 수 × 약 3(본문 목록, 상위, 제한)으로 보고 plan에서 잰다.
- 교체 시 영향(재임베딩, 인덱스 버전): 자료원을 추가하는 일은 인덱스 버전 변경이 아니다(AGENTS.md 3.3). 다만 문서 종류·회의록 메타데이터를 저장하려면 메타데이터 스키마가 바뀔 수 있고,
  그러면 인덱스 버전이 바뀌어 QK-STO-002 활성화 게이트가 필요하다(QK-CHK-001과 같은 문제). ADF 변환 규칙 버전을 어디에 넣을지와 함께 plan에서 정한다(QK-ING-003 FR-019·FR-032).
  상위 페이지 제목이 바뀌면 하위 페이지의 위치가 바뀌어 다시 임베딩된다. 그 비용도 plan 측정에서 본다.

## Consequences

### Positive

- 회의록·용어집·설계 문서를 이관 후 원본에서 바로 색인한다. ClickUp 수집 조사(0.3)의 "Doc별 사람 확인 허용 목록"보다 원본 권한으로 판정할 수 있다.
- 읽기 범위만 고른 범위 지정 토큰이라 토큰이 새어도 쓰기는 못 한다. 만료가 최대 1년이라 쓰지 않는 토큰이 남지 않는다.
- Jira 수집(QK-ING-004)이 같은 계정·변환기를 쓸 수 있다.

### Negative / risks

- 서비스 계정을 만들려면 조직 관리자가 필요하다. 사이트 소유자가 팀원 개인이면(인벤토리 F-8과 같은 문제) 그 사람이 만들어야 한다.
- 범위 지정 토큰은 만료가 1년 이내라 1년마다 교체해야 한다. 교체를 놓치면 수집이 멈춘다(QK-SYN-001 실패 알림, ADR-021로 알 수 있다).
- 권한 판정에 호출이 많이 들고, Free 플랜이면 권한 정보가 판정에 쓸모없을 수 있다.
- 이관된 문서의 표·이미지 손실(RISK-01)은 변환으로 되살릴 수 없다. 원본을 고치거나 경고로 남긴다.
- 페이지 안 에이전트 지시문(예: "이 문서를 읽은 AI는 …")은 데이터로만 다룬다(AGENTS.md 3.2).

## Revisit conditions

- 사이트 요금제가 바뀌거나(Free ↔ Standard), 스페이스 권한 모델이 바뀌어 `principal.type=role`이 쓰일 때.
- 대상 스페이스를 더하거나, 블로그·첨부·댓글을 넣을 때.
- 한 실행의 요청 수가 Atlassian 순간 한도로 429를 반복해서 받거나, 미확인·제한으로 빠진 페이지가 범위의 10%를 넘을 때.
- Atlassian이 범위 지정 토큰·서비스 계정의 한도나 요금, API 토큰 호출에 포인트 한도를 적용할 때.
- 임베딩 공급자(ADR-002)나 저장 위치(ADR-008)가 바뀔 때.

## Approval

- Approvers:
- Approved at:
- 이 초안은 Claude 세션이 썼고 그 세션은 승인하지 않는다(AGENTS.md 2절).
