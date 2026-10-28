# Contract: Confluence 어댑터와 전송

근거: [research.md](../research.md) R-02~R-07, R-14, R-16 | 값 형식: [data-model.md](../data-model.md)

## 종류와 연결

- 수집 종류 사양(`sources/kinds.py`): `confluence_pages`, 인증 필요, 범위 값 검증기(data-model 1절), 기본 허용 호스트 `("api.atlassian.com",)`, 추가 인증 항목 `ATLASSIAN_EMAIL`·`ATLASSIAN_CLOUD_ID`.
- 보안 종류 사양(`security/kinds.py`): data-model 9절.
- 대상 조립(`indexer/sync_cli.py`): 종류 → (어댑터, 전송) 팩토리 표. 어댑터는 `space`·판정 방식·확인 기록 파생 값(`site_review_valid`)·오늘 날짜를 생성 인자로 받는다.

## 전송

`HttpsTransport(auth_hosts=("api.atlassian.com",), token, authorization=<Basic 생성 함수>, default_headers={"accept": "application/json", "user-agent": …})`.
요청 기준 주소는 `https://api.atlassian.com/ex/confluence/{ATLASSIAN_CLOUD_ID}/wiki/api/v2`이다. `GET`만 보낸다(세션이 강제). 토큰·메일·Cloud ID·인증 헤더는 예외 메시지·로그·요약에 남지 않는다.

## `list_page`(커서 무시, 한 번에 전체)

1. `GET /spaces?keys=<space_key>`. 결과가 없거나 403·404면 `ListPage(items=(), complete=False)`. 결과의 `id`가 설정 `space_id`와 다르면 그 뒤 요청 없이 `complete=False`로 멈추고
   실제 값을 `origin`에 싣는다. 첫 실행에서 틀린 ID가 기준값으로 등록되거나 범위 키와 어긋나는 일을 막는다(FR-002a, plan 검토 P8). 저장된 기준값과 다르면 동기화가 `MISMATCH`로 보류한다.
   `type = personal`이면 그 뒤 요청 없이 `complete=False`로 멈춘다(FR-002). 스페이스 홈 ID는 응답의 `homepageId`다.
2. `judge_mode = team_group`이면 `GET /spaces/{id}/permissions`를 끝까지 받아 `team_group_read`를 정한다. 실패하면 모든 페이지가 조회 실패다.
3. `GET /spaces/{id}/pages?status=current&limit=250`를 `_links.next`로 끝까지 받는다. 다음 주소는 `_links.next`의 경로와 쿼리만 게이트웨이 기준 주소 뒤에 잇는다.
   한 쪽이라도 실패하면 `complete=False`이고 그때까지의 항목만 돌려준다. 원본 링크 기준 주소는 `_links.base`, 없으면 `ATLASSIAN_SITE_URL`, 둘 다 없으면 `complete=False`다(research R-01, R-12).
4. 상위 사슬: 각 페이지의 `parentId`·`parentType`. 폴더 상위는 `GET /folders/{id}`로 사슬을 잇는다(실행 안에서 한 번씩).
5. `GET /pages/{id}/restriction-state`(모든 페이지), `GET /folders/{id}/restriction-state`(사슬의 폴더)를 한 번씩 묻는다.
   `VIEW_RESTRICTED`면 제한, `OPEN`·`EDIT_RESTRICTED`면 제한 없음, 그 밖의 값이면 모름. 요청이 실패(2xx 아님, 전송 오류)하면 조회 실패다.
6. 항목마다 `read_restricted`를 정한다. 자신이 제한 → `self`, 상위 중 하나가 제한 → `ancestor`, 제한은 없는데 모르는 값이 있거나 사슬이 목록에 없는 페이지·페이지와 폴더가 아닌 상위에서
   끊기면 → `unknown`(규칙상 미확인), 모두 제한 없음 → `none`. 자신이나 사슬에 조회 실패가 있으면 `AccessInfo(UNKNOWN)`이다(FR-031 실패 수, plan 검토 P6).
7. 첫 단계 콘텐츠·대응표·제외 트리로 `exclusion`을 정한다(data-model 5절). `outside-home`은 상위가 없는 진짜 최상위 페이지만이다. 사슬이 끊겨 홈에 닿지 못한 페이지는
   제외하지 않고 권한 판정에 맡긴다. 읽지 못한 폴더나 다 받지 못한 목록에서 끊긴 사슬은 조회 실패(`AccessInfo(UNKNOWN)`)다(구현 검토 C1). 항목은 `source_id` 오름차순으로 정렬한다(C-07).
8. 첫 `ListPage`에 `origin=SourceOrigin(space_id, space_key, None)`.
9. `complete=False`로 돌려줄 때는 `ListPage.incomplete_reason`(새 필드, 기본 `None`)에 `space_not_found`·`space_id_mismatch`·`personal_space`·`site_base_missing`·`listing_failed` 중 하나를 남긴다.
   계획은 이 값을 `SourcePlan.incomplete_reason`으로 옮겨 요약에 보인다(plan 재검토 N4).

## `fetch_content`

`GET /pages/{id}?body-format=atlas_doc_format`. 본문 JSON을 `convert_adf`(contracts/adf-markdown.md)로 바꿔 data-model 6절의 `SourceContent`를 만든다.
본문 크기 상한은 세션의 `max_content_bytes`다. JSON이 아니거나 ADF 최상위가 `doc`가 아니면 `InvalidResponse`(그 페이지만 영구 실패).

## `check_missing`(선택 Protocol, FR-030)

ID마다 `GET /pages/{id}`(본문 없이, 상태 `current`·`archived`·`trashed`·`deleted`를 명시. 여러 값 표기와 허용 값은 구현 때 공식 문서로 확인).
200이고 `spaceId`가 설정 스페이스와 같으며 `status=current` → `PRESENT`, 다른 스페이스 → `GONE`, `status ∈ {archived, trashed, deleted}` → `ARCHIVED`, 403·404 → `GONE`,
그 밖의 상태 값·크기 초과·잘못된 응답·429·5xx·전송 오류 → `UNCERTAIN`. 계획은 ID를 한 건씩 넘긴다. 확인 중 `RunStopped`(요청 예산·실행 시간·대기·401)가 나면 이미 확인한 결과는 쓰고 남은 ID는 `UNCERTAIN`이며(구현 검토 C5)
호출자(계획)가 `COLLECTION_INCOMPLETE`와 멈춤 사유를 남긴다(research R-04).
후보에서 이미 같은 사유로 끝난 보안 내림(`SECURITY_ACCESS`)은 빼고 부른다(plan 검토 P1).

## 분류

`classify`·`rate_limit_hint`는 공통 기본 구현을 쓴다(429·`Retry-After` → 일시적 실패, 401 → 실행 정지, 403·404 → 영구 실패). 이 어댑터는 재정의하지 않는다.

## 시험(재생 응답)

`tests/unit/adapters/confluence_scenarios.py`가 합성 응답을 만든다. 시험 파일 이름은 `test_confluence_listing.py`·`test_confluence_access.py`·`test_confluence_content.py`·
`test_confluence_classify.py`·`test_confluence_missing.py`다(저장소 전체에서 겹치지 않는 이름, research R-18). 사례: 여러 쪽 목록·쪽 경계 중복, 초안 없음(status 파라미터), 개인 스페이스, 모르는 종류, 보관 스페이스,
자신·상위 페이지·상위 폴더 제한, 제한 조회 실패(403·404·429 소진), 폴더 범위 없음, 사슬 끊김, 대응표·제외 트리·홈·홈 밖, 단건 확인 네 결과, 본문 크기 초과, 잘못된 ADF.
합성 값에 실제 이름·메일·계정 ID·사이트 주소를 쓰지 않는다. 사이트 호스트는 예약 최상위 도메인의 `site.invalid`를 쓴다.
