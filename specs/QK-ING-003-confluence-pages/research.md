# Research: QK-ING-003 Confluence 페이지 수집

**Date**: 2026-10-28 | **Spec**: [spec.md](spec.md)(2026-10-28 사람 승인) | **Plan**: [plan.md](plan.md)

표기: `(확인)`은 이 저장소 코드나 공식 문서에서 직접 본 것, `(추론)`은 그로부터 판단한 것, `(BLOCKED)`는 실측을 보류해 아직 모르는 것이다.
코드 근거는 `src/qello_knowledge/` 기준 경로다. 외부 호출은 0건, 0 Neurons다(실측 보류, R-01).

## R-01 실측 보류와 남은 사실

**Decision**: plan 실측 스크립트 [measurement/measure_confluence.py](measurement/measure_confluence.py)를 만들고 `--dry-run`만 돌렸다. 실제 원본 호출은 2026-10-28 사용자 결정으로 보류했다.
설계는 아래 사실이 어느 값이든 맞게 동작하도록 정했다. 값이 정해지면 바뀌는 것은 설정값과 기본값뿐이고 코드 구조는 그대로다.

| 모르는 사실 | 설계가 견디는 방식 | 정해지는 곳 |
| --- | --- | --- |
| `SCRUM` 스페이스 종류 값(BLOCKED) | 팀 종류 셋을 모두 허용, 모르는 값은 미확인(R-03) | 실측 또는 첫 측정(FR-027) |
| 스페이스 ID(BLOCKED) | 설정 `space_id`. 비활성 동안은 비워 둘 수 있다(R-12) | 켜기 전 사람이 설정 |
| 페이지 수·크기, 폴더 사용, 트리 깊이(BLOCKED) | 요청 수가 페이지 수에 비례(R-02). 크기 상한은 기존 `max_content_bytes` | 측정 뒤 한도 조정 |
| 보기 제한 상태가 상속 제한을 반영하는지(BLOCKED) | 모든 상위 콘텐츠의 자기 상태를 따로 보므로 어느 쪽이든 맞다(R-03) | 시험은 두 경우 모두 둔다 |
| 토큰 범위(BLOCKED, 사용자가 기억하지 못함) | 필요한 범위를 셋으로 줄였다(R-02). 없는 범위는 조회 실패 → 미확인·기준(R-05) | 첫 측정의 엔드포인트별 상태 코드 |
| 첫 단계 콘텐츠 ID와 문서 종류(BLOCKED) | 대응표는 설정값. 없으면 미분류로 색인하지 않는다(R-07) | 켜기 전 사람이 설정·확인 기록 |
| 매크로 종류, 셀 병합 표, 멘션 수(BLOCKED) | 모르는 매크로는 자리 표시+경고(R-08) | 첫 측정의 변환 경고 수 |
| 게이트웨이 응답에 `_links.base`(사이트 주소)가 오는지, `_links.next` 형태(BLOCKED) | `_links.base`가 없으면 선택 설정 항목 `ATLASSIAN_SITE_URL`을 쓰고, 둘 다 없으면 목록 불완전(R-12). `_links.next`는 경로만 게이트웨이 뒤에 잇는다(R-02) | 첫 측정 |
| 첫 색인 예상 Neurons(BLOCKED) | 공식만 정한다: Σ ceil(임베딩 입력 바이트/1.4)×1075/10⁶(`embedding/estimate.py:24-31`) | 첫 측정(FR-027, SC-010) |
| 사이트 요금제 | 사용자 답 Free(2026-10-28) → 판정 방식 `site_users`(FR-012) | 확정 |

**Rationale**: 실측 값은 모두 설정·한도·기본값에만 들어가고 구현 경로는 바꾸지 않는다. 기본 검증은 재생 응답만 쓰므로 구현과 시험은 실측 없이 진행할 수 있다.
켜기 전 사람 단계(FR-027 측정, 확인 기록)가 이 값을 채운다.

**Alternatives**: 실측 뒤 plan 작성(사용자가 보류함). 실측 없이 값을 가정해 코드에 고정(값이 틀리면 코드 변경이 필요해 버림).

## R-02 호출 흐름과 요청 수

**Decision**: Confluence REST API v2를 `https://api.atlassian.com/ex/confluence/{cloudId}/wiki/api/v2`로 부른다(범위 지정 토큰, ADR-026 [A1]). 인증은 `Basic base64(email:token)`이다.
한 실행의 요청은 다음과 같다.

| 순서 | 요청 | 횟수 | 범위 |
| --- | --- | --- | --- |
| 1 | `GET /spaces?keys=<key>` | 1 | `read:space:confluence` |
| 2 | `GET /spaces/{id}/permissions`(판정 방식 `team_group`일 때만) | ⌈할당/250⌉ | `read:space:confluence` |
| 3 | `GET /spaces/{id}/pages?status=current&limit=250`(본문 없이) | ⌈N/250⌉ | `read:page:confluence` |
| 4 | `GET /folders/{id}`(상위 사슬에 폴더가 있을 때) | F | `read:folder:confluence` |
| 5 | `GET /pages/{id}/restriction-state`, `GET /folders/{id}/restriction-state` | N + F | `read:page:confluence`, `read:folder:confluence` |
| 6 | `GET /pages/{id}?body-format=atlas_doc_format`(팀 공용 판정을 통과한 페이지만) | ≤ N | `read:page:confluence` |
| 7 | `GET /pages/{id}`(사라진 페이지 단건 확인, R-04) | 사라진 수 | `read:page:confluence` |

`Free` 사이트(`site_users`)의 정상 실행은 약 `2N + 2F + ⌈N/250⌉ + 1`요청이다(추론). 기본 한도(분당 60, 실행당 2,000요청, 1,800초, `domain/source_config.py:15-19`) (확인)로는
N이 약 880 이하여야 한 실행에 끝난다(추론). 넘으면 첫 측정 뒤 자료원 설정 `[source.limits]`로 올린다(코드 변경 없음). 목록은 한 `list_page` 호출 안에서 모두 받으므로,
중간에 실행이 멈추면(`RunStopped`) 항목 0개의 불완전 목록이 되고 내림은 일어나지 않는다(`sources/collect.py:38-41`) (확인). 다음 쪽 주소는 응답 `_links.next`의 경로와 쿼리만
게이트웨이 기준 주소 뒤에 잇는다(절대 주소로 오면 호스트를 버린다). 스페이스 홈 ID는 요청 1 응답의 `homepageId`다.
상위 페이지 사슬은 목록의 `parentId`·`parentType`으로 만들므로 `GET /pages/{id}/ancestors`와
`read:content.metadata:confluence` 범위는 쓰지 않는다. 보기 제한은 콘텐츠마다 한 번만 묻고, 하위 페이지는 실행 안에서 그 결과를 다시 쓴다(spec "설계 단계로 넘기는 것").

**Rationale**: 목록에 본문을 함께 받으면 요청이 N개 줄지만 두 가지가 걸린다. 세션은 목록 요청에도 `max_content_bytes`를 걸어(`sources/session.py:89`) 본문이 든 목록 쪽이
크기 초과로 실패할 수 있고, 팀 공용이 아닌 페이지의 본문도 받게 된다(FR-011은 허용하지만 받지 않는 편이 안전하다). 그래서 본문은 판정을 통과한 페이지만 따로 받는다.
ADR-026 "목록 응답에 본문을 함께 받을 수 있어 단건 호출이 필요 없다"는 이 결정으로 바뀐다(ADR-026 정정 대상, plan "사람 확인").

**Alternatives**: 목록에 `body-format` 포함(요청 N개 절약, 위 두 문제), `ancestors` 엔드포인트로 상위 판정(N개 요청과 범위 하나 더 필요).

## R-03 원본 권한 원값과 판정

**Decision**: 어댑터가 목록 단계에서 권한 원값을 다 계산해 `AccessInfo.raw`에 담고, 보안 필터의 Confluence 판정 함수는 원값만 읽는다(`security/kinds.py` 등록 방식, `security/screen.py:85-100`).

| 원값 키 | 값 | 출처 |
| --- | --- | --- |
| `judge_mode` | `team_group` · `site_users` | 자료원 설정 |
| `space_type` | 원본 값 그대로 | 요청 1 |
| `space_status` | 원본 값 그대로 | 요청 1 |
| `team_group_read` | `true` · `false`(`site_users`면 넣지 않음) | 요청 2, 설정의 그룹 ID와 `principal.type=group`, `operation.key=read`, `targetType=space` 비교 |
| `site_review_valid` | `true` · `false`(`team_group`면 넣지 않음) | 확인 기록의 사이트 사용자 확인일 + 90일 ≥ 오늘(UTC 날짜, R-13) |
| `read_restricted` | `none` · `self` · `ancestor` · `unknown` | 요청 5. 자신과 모든 상위 콘텐츠의 `VIEW_RESTRICTED` 여부. 응답은 왔는데 모르는 상태 값이거나, 사슬이 목록에 없는 페이지·페이지와 폴더가 아닌 상위에서 끊기면 `unknown` |
| `ancestor_count` | 정수 문자열 | 상위 사슬 길이 |

판정: 팀 종류(`global`·`collaboration`·`knowledge_base`) ∧ `space_status=current` ∧ (`team_group_read=true` 또는 `site_review_valid=true`) ∧ `read_restricted=none`이면 팀 공용,
`read_restricted`가 `self`·`ancestor`면 제한, 그 밖(모르는 종류·상태, 원값 누락, 모르는 키)은 미확인이다. 규칙 이름은 `confluence-access-v1`이다.

**조회 실패의 표시**: 스페이스 권한·보기 제한·폴더 요청이 실패(2xx가 아님, 전송 오류)한 페이지(자신이나 상위 사슬 중 하나라도)는
`AccessInfo(status=UNKNOWN)`(원값 없음)로 넘긴다. 응답은 받았지만 값을 모르거나 사슬이 구조적으로 끊긴 경우는 원값 `read_restricted=unknown`으로 넘겨 규칙이 미확인을 정한다
(plan 검토 P6. 그래야 FR-031의 "규칙이 모르는 값은 세지 않는다"와 맞고, 구조 때문에 매번 불완전이 되는 일이 없다). 이미 `AccessStatus.UNKNOWN`이면 판정과 무관하게 미확인이 된다(`security/screen.py:88-89`) (확인).
그래서 판정 기록의 `access_raw`가 비어 있으면 "원본이 권한을 알려 주지 못함", 원값이 있는데 미확인이면 "규칙이 미확인을 정함"으로 나뉜다. FR-031의 실패 수는 앞의 것만 센다(R-05).

**Rationale**: 판정 함수는 `AccessInfo`만 받는다(`security/kinds.py:13-19`). 상속 제한을 반영하는지 모르는 `restriction-state`(R-01)도 상위마다 자기 상태를 보면 결과가 같다.
`personal` 종류는 판정까지 가지 않고 어댑터가 목록 단계에서 멈춘다(FR-002, R-02 요청 1 뒤).

**Alternatives**: 판정 함수가 설정·시계에 접근(Protocol 변경 필요, 버림). 상위 판정을 `ancestors`로(R-02).

## R-04 사라진 페이지 단건 확인(FR-030)

**Decision**: 어댑터 계약에 선택 Protocol `MissingItemChecker.check_missing(session, config, source_ids) -> Mapping[str, MissingCheck]`를 더한다(`ports/source.py`).
`MissingCheck`는 `GONE`(접근 거부·없음·다른 스페이스), `ARCHIVED`(보관·휴지통), `PRESENT`(현재·같은 스페이스), `UNCERTAIN`(일시적 실패) 넷이다.
`sync/plan.py:172-184`의 일반 내림 후보를 모은 뒤, 어댑터가 이 Protocol을 구현할 때만 부른다.

| 결과 | 결정 |
| --- | --- |
| `GONE` | 보안 내림 `SECURITY_ACCESS`(접근 범위 미확인). 비율 검사의 일반 내림 수에 들어가지 않는다 |
| `ARCHIVED` | 지금처럼 `SOURCE_MISSING` 일반 내림 |
| `PRESENT` | 내리지 않고 그 자료원에 `COLLECTION_INCOMPLETE` 보류를 더한다(목록 경합) |
| `UNCERTAIN` | 이번 실행에서 그대로 둔다 |

- 후보에서 빼는 것: 이미 같은 사유로 끝난 보안 내림(`_settled_security_takedown(previous, SECURITY_ACCESS)`). 빼지 않으면 볼 수 없게 된 페이지가 매 실행 단건 확인되고 내림 결정이 반복되어
  `purge` 수에 쌓이고, 비율 보류가 계속 걸린다(plan 검토 P1) (확인: 끝난 보안 내림은 판정이 있는 문서만 `settled`에 들어간다, `sync/plan.py:129`).
- 단건 요청은 `GET /pages/{id}?status=current&status=archived&status=trashed`로 상태를 명시한다(상태를 빼면 휴지통 페이지가 404로 올 수 있다, 추론). 여러 값 표기 형식은 구현 때 공식 문서로 확인한다.
- 실패 대응: 403·404 → `GONE`, 다른 스페이스 → `GONE`, `archived`·`trashed`·`deleted` → `ARCHIVED`, `current`·같은 스페이스 → `PRESENT`, 그 밖의 상태 값·크기 초과·잘못된 응답·429·5xx·전송 오류 → `UNCERTAIN`.
  확인 중 실행이 멈추면(`RunStopped`: 요청 예산, 실행 시간, 대기, 인증 실패) 남은 후보는 모두 `UNCERTAIN`이고 그 자료원에 `COLLECTION_INCOMPLETE`를 더하며 멈춤 사유를 요약에 남긴다(plan 검토 P7).
- `PRESENT`나 확인 중 멈춤으로 불완전이 되면 계획의 `listing_complete`를 거짓으로, `incomplete_reason`(`missing_check_present`·`missing_check_stopped`)을 남긴다(plan 검토 P13).

**Rationale**: 계획 단계는 `SyncTarget`의 어댑터와 세션을 쓸 수 있다(`sync/plan.py:27-36`) (확인). GitHub 어댑터는 이 Protocol이 없으므로 요청 수와 결정이 그대로다.
`COLLECTION_INCOMPLETE`는 `SOURCE_MISSING`만 막고 보안 숨김은 그대로 두므로(`domain/sync.py:93`) spec Edge Case(목록 경합)와 맞다. 미리 보기도 같은 함수를 쓰므로 미리 보기에서도
읽기 요청이 나간다(추론, `indexer/sync_cli.py:237-247`). 계약 문서에 적는다.

**Alternatives**: 목록에서 빠지면 모두 보안 내림(보관 페이지까지 보안 내림, 버림). 일반 내림 그대로(볼 수 없게 된 페이지가 비율 검사에 막혀 남는다, 1차 검토 H1).

## R-05 권한 조회 실패 기준(FR-031)

**Decision**: 보안 종류 등록(`KindSecurityPolicy`)에 `lookup_failure_threshold: float | None = None`을 더하고 Confluence만 `0.10`으로 둔다.
`plan_source`가 이번 목록에서 `ACCESS_HELD`이면서 `access_raw`가 빈 판정 수를 세어 목록 항목 수의 10%를 넘으면 다음을 한다.

- 그 자료원에 `COLLECTION_INCOMPLETE` 보류를 더한다(일반 내림 `SOURCE_MISSING` 보류).
- 그 판정들로 생긴 보안 내림만 `delete_bodies=False`로 만든다(숨김은 하고 본문은 남긴다). 다른 판정(비밀값 차단 등)의 보안 내림은 그대로 `delete_bodies=True`다.
- 이 문서들은 비율 검사의 `purge` 수에 넣지 않는다. 지난 실행에서 남은 `purge_pending` 때문에 `pending` 집합에 들어 있어도 이번 실행에서 조회 실패면 뺀다.
  `--confirm-takedown` 실행에서도 이 문서들에는 `PURGE`를 붙이지 않는다(`sync/plan.py:185-204`, plan 검토 P2). 그래서 대량 조회 실패가 다른 문서의 본문 삭제까지 비율 보류로 막지 않고,
  조회 실패 문서의 본문은 확인 실행에서도 지워지지 않는다(FR-031 "본문 삭제 0건").
- 계획의 `listing_complete`를 거짓으로, `incomplete_reason=access_lookup_threshold`를 남긴다.
- 목록 자체가 불완전한 실행에서는 기준 비율과 관계없이 모든 조회 실패 문서의 본문을 남긴다. 다 받지 못한 목록에서 끊긴 사슬도 조회 실패로 센다(구현 검토 C1).

**Rationale**: 보류를 자료원 단위로 걸면 `constrain`이 비밀값 문서의 본문 삭제까지 끈다(`sync/decide.py:50`) (확인, 재검토 R1). 문서 단위 `delete_bodies=False`는
`SourcePlan` 검증을 통과한다(보안 내림은 `SECURITY_HIDE`만 요구) (확인). 본문이 남으면 `purge_pending`이 남고, 다음 실행에서 조회가 성공해 팀 공용이면 다시 색인되고,
여전히 미확인이면 그때 `delete_bodies=True`로 지운다(`_settled_security_takedown`이 `purge_pending`이 남은 동안 거짓, `sync/plan.py:39-46`).
`lookup_failure_threshold`가 없는 GitHub는 계산하지 않으므로 결정이 그대로다.

**Alternatives**: 새 `HoldReason`(자료원 단위라 위 문제). `AccessScope`에 값 추가(저장 열·판정 불변식 변경이 커서 버림).

## R-06 위치·제목·링크

**Decision**:
- `SourceItem.location`은 `<스페이스 키>/<첫 단계 제목>/…/<페이지 제목>`이다(FR-004 "스페이스 키와 첫 단계부터의 제목 경로"). 제목 조각은 앞뒤 공백을 지우고,
  `/`를 `／`(U+FF0F)로, 빈 제목을 `(제목 없음)`으로, `.`·`..`만인 제목을 `．`·`．．`로 바꾼다. 경로 규칙(`PurePosixPath`, glob)에서 구분자로 오해되지 않게 하려는 것이다.
- `SourceItem.title`과 `SourceContent.title`은 페이지 제목 원문이다. 변환 결과 첫 줄에 `# <제목>`을 넣어 인용 제목이 페이지 ID나 위치로 대체되지 않게 한다
  (`generation/render.py:55-63`는 첫 청크 `heading_path` → `locator["path"]` 순서로 제목을 고른다) (확인). 검색 헤더의 제목 중복은 `chunking/header.py:28`이 없앤다 (확인).
- `SourceItem.url`은 응답의 `_links.base` + `_links.webui`다. 사이트 호스트(`*.atlassian.net`)는 저장소에 적지 않고 실행 중 응답에서 얻는다.
- 변환기가 남기는 링크 주소(FR-018)는 `https`이고 다음 둘 중 하나일 때만이다(2026-10-28 사용자 결정, plan 검토 P5).
  (1) 호스트가 실행 중 얻은 사이트 호스트와 같고, 경로가 사람·개인 스페이스를 가리키지 않는다(`/wiki/people/`, 경로 조각이 `~`로 시작, `/wiki/display/~`) (plan 검토 P4).
  (2) 호스트가 보안 필터에 등록된 공개 링크 호스트(모든 종류의 `public_link_hosts` 합집합, 지금은 `github.com`)다.
  남길 때도 쿼리와 조각(`?…`, `#…`)은 버린다. 그 밖은 링크 텍스트만 남긴다. spec의 "공개 웹 주소"는 이 등록 목록으로 해석한다. 우리 서비스의 서버 주소는 형식만으로 공개 주소와
  가를 수 없어서다. 필요한 호스트는 등록 목록에 더해 넓힌다(보안 규칙 버전이 바뀐다).

**Rationale**: `location`은 검색 헤더·임베딩 캐시·변경 판정·경로 제외·비밀값 검사에 두루 쓰인다(조사 결과, `chunking/header.py:27-29`, `sync/keys.py:9-12`, `security/screen.py:55,70-80`).
제목 경로가 GitHub의 파일 경로에 해당한다. 상위 제목이 바뀌면 하위 위치가 모두 바뀌어 다시 처리된다는 점은 spec Edge Case가 받아들였다.
기본 제외 규칙(`domain/exclusions.py`)은 파일 경로용이라 `build`·`secrets` 같은 제목의 페이지를 제외할 수 있다(추론). 덜 수집하는 방향이라 그대로 두고,
측정(FR-027)의 `PATH_EXCLUDED` 수로 사람이 확인한다(plan "사람 확인").

**Alternatives**: `location`을 `<키>/<페이지 ID>`로(제목 경로 문맥을 잃고 spec FR-004와 다름). 기본 제외를 Confluence에서 끄기(QK-SEC-001 동작 변경이라 이 작업에서 하지 않음).

## R-07 미분류·제외 트리·홈(FR-020a, FR-021a)

**Decision**: 어댑터가 목록 단계에서 상위 사슬로 첫 단계 콘텐츠를 찾고, 다음 페이지에 `SourceItem.exclusion`(새 필드, 기본 `None`)을 채운다.

| `exclusion` 값 | 대상 |
| --- | --- |
| `space-home` | 스페이스 홈 페이지 자체 |
| `outside-home` | 홈의 하위가 아닌 최상위 페이지 |
| `unclassified` | 대응표에 없는 첫 단계 아래 페이지 |
| `not-indexed-type` | 대응표에서 "색인 안 함"인 종류 |
| `excluded-tree` | 제외 트리 ID 목록의 콘텐츠와 그 하위 |

보안 필터 PATH 단계(`security/screen.py`)는 `exclusion`이 있으면 `PATH_EXCLUDED`(규칙 `source-exclude:<값>`)로 판정한다. 그 뒤는 기존 경로대로
보안 내림(`SECURITY_PATH`, 본문 삭제, 비율 검사는 본문 삭제에만 적용)이다(`sync/plan.py:119-140`) (확인). 이 페이지들은 목록에 남으므로 사라진 자료 확인(R-04) 대상이 아니다.
GitHub 어댑터는 이 필드를 채우지 않으므로 판정이 그대로다.

**Rationale**: 대응표와 제외 목록은 ID 기준이라 경로 glob 제외(`source_excluded`)로 표현할 수 없다. 판정을 어댑터가 하고 보안 필터는 표시만 따르면 보안 필터에 Confluence 지식이 들어가지 않는다.
첫 단계 페이지 자신은 그 종류에 속한다(FR-020).

**Alternatives**: 목록에서 빼기(사라진 자료로 오인되어 단건 확인·일반 내림으로 가므로 FR-020a와 다름).

## R-08 ADF → Markdown 변환

**Decision**: 본문은 ADF(`atlas_doc_format`)로 받아 표준 라이브러리만 쓰는 순수 함수 `convert_adf(doc, *, title, site_host, public_link_hosts, doc_type) -> ConvertResult`로 바꾼다.
위치는 `adapters/atlassian_adf.py`다(Jira 설명·댓글도 ADF라 QK-ING-004가 다시 쓸 수 있다, ADR-026). 규칙 버전은 `adf-md-v1`이다. 규칙표는 [contracts/adf-markdown.md](contracts/adf-markdown.md).

- 제목·문단·목록·표·코드 블록(언어)·인용·구분선·링크 텍스트는 대응 Markdown으로, `panel`·`expand`·`nestedExpand`는 제목 줄과 본문으로 펼친다(FR-014).
- `extension`·`bodiedExtension`·`inlineExtension`과 모르는 노드는 `[매크로: <키>]` 자리 표시와 `UNSUPPORTED_BLOCK` 경고(FR-015). 매크로 설정값은 넣지 않는다.
- 셀 병합·표 안 표는 셀 내용을 행 순서 목록으로 펼치고 `TABLE_FLATTENED` 경고(FR-016).
- `mention`은 `attrs.text`의 표시 이름만(`@` 제거), `mailto:` 링크는 `[메일 주소]`, 사용자 정보를 보여 주는 매크로는 다른 매크로처럼 `[매크로: <키>]`(설정값 없음),
  `mediaSingle`은 `[이미지]`, `mediaGroup`의 항목은 `[첨부: <attrs.alt>]`(없으면 `[첨부]`), `status`·`date`·`emoji`는 표시 텍스트(FR-017).
- 텍스트가 제목 줄과 자리 표시뿐이면 본문을 빈 문자열로 둔다. 청커가 `EMPTY`를 돌려주고 수집 요약의 "본문 없음"으로 센다(FR-032, spec Edge Cases).
- 본문은 `body.atlas_doc_format.value`의 JSON 문자열을 한 번 더 파싱해 얻는다.
- 같은 입력이면 바이트 단위로 같은 출력이다. 딕셔너리 순서에 기대지 않고, 줄바꿈은 `\n`, 끝에 줄바꿈 하나(FR-019).
- 경고는 `(종류, 블록 순번)`만 담고 원문을 담지 않는다.

**Rationale**: ADF는 노드 종류가 정해진 JSON이라 HTML(`storage`)보다 결정적이다(ADR-026). 청커는 Markdown만 받는다(`chunking/service.py:88-98`) (확인).

**Alternatives**: `storage`(XHTML) 파싱(HTML 파서 의존과 매크로 표현이 복잡, 버림). 청커가 ADF를 직접 받기(QK-CHK-002 변경, spec이 금지).

## R-09 변경 판정 재료(spec R2, FR-019)

**Decision**: spec의 "변경 키"는 이 코드에서 문서별 변경 판정 재료인 `chunk_input_hash`(`sync/keys.py:9-12`)다. `SourceItem.change_key`는 결정에 쓰이지 않는다(`sync/decide.py:6-17`) (확인).
`chunk_input_hash`에 선택 인자 `extra: str | None = None`을 더하고, `None`이면 지금과 같은 바이트열을 만든다. Confluence는 `extra`에 변환 규칙 버전, 문서 종류, 회의록 메타데이터를
정렬된 JSON으로 넣는다(`SourceContent.fingerprint_extra`, 새 필드). 변환 규칙 버전·문서 종류가 바뀌면 그 Confluence 문서만 `INPUT_CHANGED`로 다시 처리된다.

`SourceItem.change_key`(FR-004)는 `<버전 번호>:<제목 sha256 앞 12자>`다. 제목만 바뀌었을 때 버전 번호가 오르는지 몰라도(R-01) 판별값이 바뀐다. `change_key_kind`는 `VERSION`이다.

**Rationale**: 청킹 규칙 버전에 넣으면 전역 인덱스 버전이 바뀌어 GitHub 문서까지 다시 처리된다(spec R2 결정). `extra=None`이면 GitHub 지문이 그대로라 SC-013·SC-014를 지킨다.
통과한 문서는 매 실행 본문을 받으므로(QK-SYN-001 FR-005) 본문이 바뀌면 `content_hash`로도 잡힌다.

**Alternatives**: `version_for`에 넣기(저장되는 `chunking_version` 열과 실행 기록까지 바뀜). 변환 규칙 버전을 넣지 않기(출력이 같아도 메타데이터가 바뀐 경우를 놓침).

## R-10 메타데이터 저장과 스키마 버전(FR-032, spec N9)

**Decision**: 문서 종류와 회의록 메타데이터는 Confluence 청크의 `locator["confluence"] = {"page_id", "doc_type", "meeting": {"date", "kind", "spec_ids"} | null}`에 둔다.
QK-CHK-001이 코드 메타데이터를 `locator["code"]`에 둔 방식과 같다(QK-CHK-001 research R-11, `chunking/code/service.py:95-97`) (확인). 저장 스키마 마이그레이션은 없다.
`artifact_kind`는 `confluence_page`다(`sync/execute.py:151`, 검색 필터 `SearchFilter.artifact_kinds`로 거를 수 있다).

메타데이터 스키마 버전은 `metadata_schema_version(code, confluence)`로 넓힌다. 둘 다 꺼짐이면 `meta-v1`, 코드만 켜짐이면 `meta-v2`(지금 값), Confluence가 켜지면 뒤에 `+cf1`을 붙인다
(`meta-v1+cf1`, `meta-v2+cf1`). "Confluence 켜짐"은 다음 중 하나다(2026-10-28 사용자 결정, plan 검토 P3).

- `config/sources.toml`에 `confluence_pages` 종류의 활성 자료원이 있다.
- 저장소에 `confluence_pages` 종류의 자료원 정체성이 등록돼 있다(`qk.sync_source`, 첫 색인 때 등록, `sync/run.py:113-130`). 한 번 색인하면 끈 뒤에도 켜짐으로 본다.

뒤의 조건이 없으면, 켜서 색인하고 활성화한 뒤 끄는 순간 계산 버전이 옛 값으로 돌아가 `INDEX_MISMATCH`가 되고, 이 보류는 끈 자료원의 일반 내림(`SOURCE_DISABLED`)을 막아
(`domain/sync.py:88`) (확인) Confluence 페이지가 검색에 남는다. 이 조건으로 끈 자료원의 페이지는 일반 내림으로 내려간다(자료원 전체라 내림 비율 보류에 걸리므로 `--confirm-takedown` 실행에서, GitHub 자료원 끄기와 같음). `+cf1`을 없애려면 새 인덱스 버전 절차(QK-STO-002)를 거친다.
저장소를 읽지 않는 `qk-index sources check`는 앞의 조건만 본다.

켜짐에서 계산한 인덱스 버전이 `INDEX_KEYWORD_RULES`(`domain/keyword_rules.py:17-22`)에 없으면 `qk-index sources check`·`run`·`index status/activate`가 원본 호출 전에 실패한다
(QK-CHK-001 FR-030과 같은 막기). 그래서 이 작업의 배포에서 자료원을 켜도 동작하지 않고, 켜는 변경에서 대응표 항목과 QK-STO-002 절차를 함께 한다.
메타데이터 스키마 버전을 부르는 곳은 `sync/run.py`(`current_spec`), `indexer/sync_cli.py:78-84`(`current_index_version`), `config/check.py:132-143`(`_code_checks`)다(plan 검토 P12).
코드 청킹과 Confluence가 함께 켜지면 `meta-v2+cf1`이다. 명령별 계산 순서는 다음과 같다(plan 재검토 N1).

| 명령 | 순서 |
| --- | --- |
| `qk-index sources check` | 설정 읽기 → 활성 자료원만으로 켜짐 계산 → 대응표 검사. 저장소를 열지 않는다 |
| `qk-index run`·`--preview` | 지금의 사전 검사(활성 자료원만) → 저장소 열기 → 저장된 자료원 정체성 읽기 → 켜짐(활성 ∨ 등록) 계산 → 대응표 두 번째 검사 → 원본 호출. 두 번째 검사가 실패하면 원본 요청·저장소 쓰기 0건 |
| `qk-index index status`·`activate` | 설정 읽기 → 저장소 열기 → 저장된 자료원 정체성 읽기 → 켜짐 계산 → 현재 인덱스 버전 계산 |
| `qk-index check`(`config/check.py` `_code_checks`) | 환경값만 안다. 코드 청킹이 켜졌을 때 코드만 켜진 버전(`meta-v2`)이나 Confluence와 함께 켜진 버전(`meta-v2+cf1`) 중 하나라도 대응표에 있으면 통과하고, 정확한 값은 자료원 쪽 검사가 본다. 둘 다 없으면 지금처럼 `CODE_INDEX_VERSION_UNREGISTERED`(QK-CHK-001 시험 그대로) |

**Rationale**: `locator`는 SQL이 구조를 전제하지 않고 검색 결과·문맥으로 그대로 돌아온다(`0002_search_functions.sql`, `0005_retrieval.sql:68-71`) (확인).
꺼짐 배포에서 `meta-v1`·`iv-4c0bc4fcc642`·`chk-md-20d966f730bb`가 그대로다(SC-014). 켜는 신호가 환경값이 아니라 자료원 설정이라 검사를 자료원 설정을 읽은 뒤에 둔다
(`indexer/sync_cli.py:202-205` 뒤, `build_runtime` 앞).

**Alternatives**: 새 열과 마이그레이션(`Provenance` 반환 형식 변경, QK-CHK-001 R-11에서 버린 안). 메타데이터를 본문 텍스트에만(필터 불가, spec N9에서 사람이 버림).

## R-11 문서 종류·회의록·용어집

**Decision**:
- 문서 종류 대응표는 자료원 설정 `doc_types = { "<첫 단계 콘텐츠 ID>" = "<종류>" }`이고, 종류 값은 `회의록`·`용어집`·`기능 명세`·`설계 문서`·`API 문서`·`디자인 문서`·`개발 규칙`·`색인 안 함`이다
  (0.4 작성 규칙 1.1의 종류, FR-020). 실제 ID는 BLOCKED(R-01)라 비활성 등록에서는 빈 표다.
- 회의록: 본문 첫 표(ADF `table`)에서 첫 열이 `일시`·`회의 종류`·`관련 명세 ID`인 행의 둘째 열 텍스트를 읽는다. `일시`는 `YYYY-MM-DD`일 때만 날짜로 쓰고, 아니거나 없으면
  `MEETING_METADATA_MISSING` 경고를 붙이고 `meeting=null`이다. `관련 명세 ID`는 쉼표로 나누고 `없음`은 빈 목록이다(0.4 작성 규칙 2.2). 표는 본문에 그대로 남는다.
- 용어집: 머리글이 `용어 | 정의 | 동의어·약어·영문 | 코드 식별자·API 경로 | 관련 문서`와 정확히 같은 표는 행마다 `## <용어>` 절과 나머지 열을 `- <머리글>: <값>` 목록으로 바꾼다.
  청커는 절마다 청크를 만든다(`chunking/split.py:65-83`) (확인). 머리글이 다르면 그대로 두고 `NOT_GLOSSARY` 경고(FR-023).

**Rationale**: 0.4 작성 규칙의 템플릿이 이관 뒤에도 유지된다고 spec이 가정했다. 실제와 다르면 측정 경고 수로 드러난다.

## R-12 자료원 설정 형식과 인증 설정(FR-025a, FR-028, 재검토 R5)

**Decision**:
- `SourceKindSpec`(`sources/kinds.py`)에 종류별 범위 값 검증기 `scope_schema`를 더한다. GitHub는 지금 규칙(`repo` 정규식, `ref` 문자열)을 그대로 옮긴다.
  `confluence_pages`의 범위 값은 `space_key`(문자열, `~` 시작 금지), `space_id`(숫자 문자열, 비활성이면 빈 값 허용), `judge_mode`(`team_group`·`site_users`),
  `team_group_id`(`team_group`일 때 필수), `doc_types`(표), `exclude_trees`(문자열 목록)다. `include`는 `["**"]` 하나로 고정한다(FR-021a).
  `SourceScope.extra`는 지금 `(키, 문자열)` 쌍이라, 표·목록 값은 정렬된 JSON 문자열로 정규화해 담는다(GitHub 값은 그대로).
- `scope_key`(`sync/keys.py:35-44`)에 `confluence_pages:<space_id>` 분기를 더한다(FR-002a).
- 설정 항목 `ATLASSIAN_API_TOKEN`·`ATLASSIAN_EMAIL`·`ATLASSIAN_CLOUD_ID`를 INDEX 진입점의 비밀 항목(`secret=True`, `required=False`)으로 등록한다(`config/registry.py`).
  선택 항목 `ATLASSIAN_SITE_URL`(비밀, 필수 아님)은 응답에 `_links.base`가 없을 때만 원본 링크의 기준 주소로 쓴다(R-01, plan 검토 P9). 사이트 주소는 저장소에 적지 않는다.
  메일과 Cloud ID는 비밀값은 아니지만 계정 정보·내부 식별값이라 설정 보고에 값이 나오지 않게 비밀로 둔다. 자료원 설정 `auth`는 지금처럼 문자열 하나(`ATLASSIAN_API_TOKEN`)이고,
  나머지 둘은 종류 사양이 이름을 고정한다(`SourceKindSpec.extra_auth`). 켜진 Confluence 자료원이 있는데 셋 중 하나라도 없으면 `sources check`가 원본 호출 전에 실패한다.
- 대상 조립은 `indexer/sync_cli.py`의 `github_targets`를 종류별 팩토리 표로 일반화한다(`sources`는 `adapters`를 가져올 수 없다, `sources/__init__.py:1-4`) (확인).

**Rationale**: 지금 설정 형식은 최상위·범위 키와 값 형식이 고정돼 있어(`sources/config.py:96-140`) 대응표와 목록을 담을 곳이 없다(재검토 R5) (확인).
`GITHUB_API_TOKEN`의 `required=True`는 바꾸지 않는다(GitHub 동작 불변).

**Alternatives**: 새 최상위 표 `[source.confluence]`(설정 키 검증을 종류별로 크게 바꿔야 함). `auth`를 목록으로(모든 자료원의 `auth` 검증이 바뀜).

## R-13 개인 정보 확인 기록(FR-021, FR-025, FR-025a, FR-012)

**Decision**: `sources/scope_review.py`의 범위 키 목록(67행)과 `extra` 복원(90행)을 종류 사양 기반으로 바꾼다. Confluence 기록에는 다음이 더 있다.

- `scope`: 설정의 범위 값과 같은 키(`space_id`, `space_key`, `judge_mode`, `team_group_id`, `doc_types`, `exclude_trees`, `include`).
- `team_member_names = "허용"`: 없으면 켜진 Confluence 자료원의 검증이 실패한다(FR-021, 재검토 N11).
- `result`: `"팀원 이름 외 개인 정보 없음"` 또는 `"개인 정보 트리 제외함"`. 뒤의 것이면 `moved_to_exclude = [{ id, reason }]`가 있어야 하고 각 ID가 `exclude_trees`에 있어야 한다.
- `site_users = { reviewed_on, user_count }`: `judge_mode = "site_users"`일 때 필수. 판정 원값 `site_review_valid`는 `reviewed_on + 90일 ≥ 오늘(UTC 날짜)`이다.
- GitHub 기록의 형식·`result` 값·검증은 그대로다(SC-007).

판정 방식과 기록 파일의 sha256은 보안 규칙 버전 재료에 넣는다(FR-012). `load_policy`에 종류별 재료를 넘기는 인자를 더하고, `run_command`가 확인 기록을 읽은 뒤 넘긴다(`security/policy.py:41-58`).

**Rationale**: 날짜 판정은 실행 시각이 필요한데 판정 함수는 원값만 받으므로(R-03) 대상 조립 때 계산해 어댑터에 넘긴다. 만료되면 모든 페이지가 규칙상 미확인(원값 있음)이 되어
숨겨지고, FR-031의 실패로 세지 않는다(R-05).

**Alternatives**: 만료 시 자료원 정지(색인된 페이지가 검색에 남아 FR-012와 다름).

## R-14 전송과 인증 헤더

**Decision**: `HttpsTransport`(`adapters/http.py:31-77`)에 키워드 인자 `authorization: Callable[[], str] | None`과 `default_headers`를 더한다. 기본값은 지금 동작
(`Bearer <token>`, `x-github-api-version` 고정)을 그대로 만든다. Confluence는 `Basic` 값을 만드는 함수와 `accept: application/json`을 넘긴다. 허용 호스트는 `api.atlassian.com` 하나다.

**Rationale**: 인증 방식과 고정 헤더만 다르고 나머지(리다이렉트 금지, 크기 절단, 오류 변환)는 같다. GitHub 헤더가 바이트 단위로 같은지 기존 시험이 지킨다.

**Alternatives**: Confluence 전용 전송 복제(같은 보안 동작을 두 곳에서 지켜야 함).

## R-15 판정 기록 출력 규칙(FR-011, SC-004, 재검토 N4·R3)

**Decision**: `KindSecurityPolicy`에 `opaque_item_fields: bool = False`를 더하고 Confluence만 `True`로 둔다. `policy.output_context(kind)`를 거쳐 `OutputContext`로 넘기고,
`SecurityVerdict.to_dict`가 이 값이 참이면 판정과 무관하게 `title`·`location`·`url`을 `None`으로 둔다. 측정 출력(`devtools/measure.py`)의 경로·경고 위치도 같은 값을 따른다.

**Rationale**: spec은 제한·미확인 판정 기록과 모든 측정 출력에서 이 값을 비우라고 한다. 판정 기록에서도 모두 비우면 규칙이 하나로 줄고 더 엄격하다. 페이지는 `source_id`(페이지 ID)로 가리킨다.
동기화 기록은 이미 `source_id`만 담는다(`sync/plan.py:59`, `sync/report.py`) (확인). GitHub 값은 기본값 `False`라 그대로다.

**Alternatives**: 제한·미확인만 비우기(규칙이 판정마다 갈라짐).

## R-16 한도와 응답 분류

**Decision**: `classify`·`rate_limit_hint`는 기본 구현(`domain/source.py:298-335`)을 쓴다. 429는 일시적 실패와 `Retry-After`, 401은 실행 정지, 403·404는 그 요청의 영구 실패다.
목록·스페이스 요청의 403·404는 목록 불완전이고, 페이지·폴더 단위 요청의 실패는 그 페이지의 조회 실패(R-03) 또는 본문 영구 실패다(FR-026). 호출 한도 기본값은 QK-ING-001 기본값이다.

**Rationale**: Atlassian 한도 문서는 429와 `Retry-After`를 쓴다(ADR-026 [A5]). 범위가 빠진 토큰의 응답이 403인지 401인지는 BLOCKED(R-01)다. 401이면 실행 전체가 멈추고, 403이면 해당 단계만 실패한다.

## R-17 측정 도구(FR-027, SC-010)

**Decision**: `qk-dev source measure`를 종류별로 일반화한다. 종류 제한(`devtools/measure.py:42-43`)과 GitHub 고정 필드를 종류별 요약으로 바꾸고, Confluence 측정은 비활성 자료원도 허용한다
(확인 기록 필수, 저장·임베딩 없음). 지금 설정 읽기는 비활성 자료원의 범위를 파싱하지 않고(`sources/config.py:91-92`) 확인 기록 대조도 건너뛴다(`sources/scope_review.py:99`) (확인).
그래서 측정 준비(`prepare_source`)가 이름을 준 비활성 Confluence 자료원 하나만 활성처럼 범위를 파싱하고 확인 기록을 대조하는 함수를 따로 쓴다. 일반 설정 읽기와 `sources check`의
비활성 처리, GitHub 측정(활성만)은 그대로다(plan 검토 P10). 출력에는 요청 수, 소요 시간, 페이지 수, 본문 총·최대 바이트, 판정별 수, 변환 경고별 수, 미분류 수, 예상 Neurons(실제 청킹의 `embedding_text`에
`estimated_neurons` 적용, 캐시 전 상한)를 담고 페이지는 ID로만 가리킨다. plan 실측 스크립트는 켜기 전 사람이 원하면 따로 돌릴 수 있게 남긴다.

**Rationale**: FR-027은 첫 실제 색인 전에 측정을 요구하고, 켜기는 사람 단계다. 비활성 상태에서 잴 수 있어야 순서가 맞는다.

## R-18 시험 자료

**Decision**: GitHub처럼 시나리오 빌더(`tests/unit/adapters/confluence_scenarios.py`)가 합성 응답을 코드로 만들어 `ReplayTransport(exchanges)`에 넣는다(`adapters/replay.py:12-41`) (확인).
ADF 변환 시험은 `tests/fixtures/confluence/adf/*.json`과 기대 Markdown `*.md`를 짝으로 둔다(사람이 쓴 기대값, SC-003). 합성 자료에는 실제 이름·메일·계정 ID·사이트 주소를 쓰지 않는다.
공통 계약 시험은 서브클래스 하나를 더한다(항목 3건 이상 필요, `tests/contract/source_adapter_contract.py`) (확인).
`tests/unit/adapters/` 등은 `__init__.py`가 없어 시험 파일 이름이 저장소 전체에서 겹치면 수집이 실패한다. 새 시험 파일 이름에는 모두 `confluence`·`atlassian`을 넣었고 겹치지 않음을 확인했다(plan 검토 P11).

## R-19 보안 규칙 버전 변화

**Decision**: Confluence 종류를 보안 종류 표에 등록하면 꺼진 배포에서도 보안 규칙 버전 값이 바뀐다(`security/policy.py:52-55`, 종류 목록이 재료) (확인).
이 값은 실행 기록과 판정 기록에만 쓰이고 문서 결정·인덱스 버전에는 쓰이지 않는다(`sync/run.py:78,145`) (확인). 받아들이고 PR에 적는다(SC-004의 예외 문구).
