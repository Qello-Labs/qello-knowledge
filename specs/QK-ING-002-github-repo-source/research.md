# Research: QK-ING-002 GitHub 저장소 파일 수집

명세 [spec.md](spec.md)(2026-10-20 사람 승인)의 요구를 코드 구조와 GitHub REST API에 맞추는 결정을 모은다. 선행 결정은
QK-ING-001 [research.md](../QK-ING-001-source-adapter-contract/research.md)(R-번호는 `ING R-xx`로 적는다)와 QK-SEC-001
[research.md](../QK-SEC-001-security-filter/research.md)(`SEC R-xx`)를 따른다. GitHub API 동작은 공식 문서 기준이고, 실제 대상에서의 확인은
R-14 측정에서 한다(C-13).

## R-01 요청 순서와 수

- **Decision**: 한 실행의 요청은 다음 순서다. 모두 `GET`이고 `api.github.com`으로만 간다.

  | 순서 | 요청 | 얻는 것 | 횟수 |
  | --- | --- | --- | --- |
  | 1 | `/repos/{owner}/{repo}` | `visibility`, `archived` | 1 |
  | 2 | `/repos/{owner}/{repo}/commits/{ref}` | 확정 커밋 SHA, 루트 트리 SHA | 1 |
  | 3 | `/repos/{owner}/{repo}/git/trees/{tree_sha}?recursive=1` | 경로·모드·종류·blob SHA·크기, `truncated` | 1 |
  | 4 | `/repos/{owner}/{repo}/git/blobs/{blob_sha}` (원문 형식) | 파일 내용 바이트 | 범위 안 파일마다 1 |

  Phase 1 대상(포함 문서 81개)이면 한 실행이 약 84회다 `(추론)`. 1~3은 목록 조회(`list_page`)에서, 4는 본문 조회(`fetch_content`)에서 보낸다.
- **Rationale**: 트리를 재귀로 한 번 받으면 디렉터리마다 내용 조회를 하지 않아도 된다(파일 1,569개 저장소에서 목록 요청 3회). blob을 SHA로 받으면
  받은 내용이 목록의 내용 식별값과 같은지 바로 검증할 수 있다(FR-007). 커밋을 먼저 확정하면 실행 도중 브랜치가 움직여도 목록과 본문이 섞이지 않는다(FR-002).
- **Alternatives considered**: 내용 조회 API(`/contents/{path}?ref=`) — 디렉터리마다 요청이 필요하고, 경로로 받으므로 받은 내용이 목록의 blob과 같다는 보장이 약하다.
  저장소 압축 파일 내려받기 — 한 번에 받지만 크기 상한(ING-001 `max_content_bytes`)과 자료별 실패 격리를 지키기 어렵다. 브랜치 API(`/branches/{branch}`) —
  태그·커밋을 받지 못한다.

## R-02 커밋 확정과 `ref`

- **Decision**: `ref`는 브랜치·태그·커밋 SHA 어느 것이든 커밋 조회 API에 그대로 넘긴다(경로 구분자까지 퍼센트 인코딩). 응답의 `sha`가 확정 커밋, `commit.tree.sha`가
  루트 트리다. 실행마다 한 번만 확정하고, 그 실행의 모든 항목 `version`에 확정 커밋을 넣는다. 본문 조회는 blob SHA로 하므로 `ref`를 다시 쓰지 않는다.
- **Rationale**: FR-002. 본문 조회가 `ref`를 쓰지 않으니 실행 도중 새 커밋이 올라와도 영향이 없다.
- **Alternatives considered**: 본문을 `ref=main`으로 조회 — 실행 중 커밋이 바뀌면 목록과 본문이 다른 시점이 된다.

## R-03 불완전 목록 표시 — `ListPage.complete` 추가 (QK-ING-001 변경)

- **Decision**: ING-001 `ListPage`에 `complete: bool = True`를 더하고, `list_all`은 `complete=False`인 페이지를 받으면 그 페이지 항목까지 담은 뒤
  `Listing.complete=False`로 끝낸다. GitHub 어댑터는 트리 응답의 `truncated`가 참이면 받은 항목과 함께 `complete=False`를 돌려준다.
  저장소·커밋·트리 조회가 실패하면(404, 409, 422 등) 지금처럼 `SourceFailure`를 내고, `list_all`이 불완전 목록으로 끝낸다(ING-001 그대로).
- **Rationale**: FR-005. 지금 `ListPage`에는 "끝까지 못 받았다"를 담을 자리가 없고, `next_cursor=None`이면 `list_all`이 완전으로 표시한다. 기본값이 참이라
  가짜 어댑터·두 번째 가짜 어댑터·기존 시험은 바뀌지 않는다.
- **Alternatives considered**: 잘린 트리 뒤에 가짜 커서를 돌려주고 다음 호출에서 실패를 내기 — 계약 밖 꼼수이고 요청 수 계산이 헷갈린다. 잘린 트리를 하위 트리로
  나눠 받기 — Phase 1 규모(파일 1,569개, GitHub 한도 10만 항목·7 MB)에서 필요 없다(명세 Edge Cases).

## R-04 목록 항목 필드

| `SourceItem` 필드 | 값 |
| --- | --- |
| `source_kind` | `github_repo_files` |
| `source_id`, `location` | 트리의 `path`(저장소 안 경로, 앞 `/` 없음) |
| `url` | `https://github.com/{owner}/{repo}/blob/{확정 커밋}/{경로}`. 경로는 `/`를 남기고 퍼센트 인코딩 |
| `change_key`, `change_key_kind` | blob SHA, `VERSION` |
| `version` | 확정 커밋 SHA |
| `modified_at` | 없음. 커밋 시각은 파일별 수정 시각이 아니다 |
| `item_type` | `repo_file` |
| `title` | 없음(FR-004) |
| `size_bytes` | 트리의 `size` |
| `access` | R-06 |
| `origin_state` | 저장소 `archived`가 참이면 `ARCHIVED`, 아니면 `ACTIVE` |

- 트리 항목 중 `type`이 `blob`이고 모드가 `100644`·`100755`인 것만 쓴다. 심볼릭 링크(`120000`), 하위 모듈(`commit`), 디렉터리(`tree`)는 버린다(FR-003).
- 항목은 경로 순으로 정렬해 돌려준다(FR-006). 포함·제외 패턴 적용은 ING-001 `list_all`이 한다(ING R-05). 어댑터는 범위 밖 파일을 미리 거르지 않는다.
- `source_id`를 저장소 안 경로로 두면 SEC-001 경로형 식별자 규칙이 파일 이름 부분을 가리지 않는다(SEC R-07, `security/kinds.py`의 `source_id_is_path=True`).
  `url`의 호스트 `github.com`은 SEC-001에 등록된 공개 원본 링크 호스트다(FR-011).

## R-05 본문 조회와 검증

- **Decision**: blob 조회에 원문 형식(`Accept: application/vnd.github.raw+json`)을 써서 base64가 아닌 파일 바이트를 받는다. 받은 바이트로 git blob SHA
  (`sha1(b"blob " + 길이 + b"\0" + 바이트)`)를 계산해 목록의 `change_key`와 다르면 `InvalidResponse`다. 그다음 UTF-8로 엄격하게 디코드하고, 실패하면
  `InvalidResponse`다(FR-007, FR-008). 내용 형식은 확장자로 정한다: `md`·`mdx`·`markdown`은 `MARKDOWN`, `json`은 `JSON`, 코드 확장자는 `CODE`, 그 밖은 `TEXT`.
- **Rationale**: base64 JSON은 크기가 약 1.33배라 ING-001 응답 크기 상한(`max_content_bytes`, 요청마다 적용)에 파일 크기보다 먼저 걸린다. 원문 형식이면
  목록 크기 검사(ING-001 `fetch_contents`)와 실제 응답 크기가 같다. SHA 검증은 응답이 다른 파일이거나 잘린 경우를 잡는다.
- **Alternatives considered**: base64 JSON 응답 — 위 크기 문제. 내용 해시(`sha256`)만 비교 — 목록이 sha256을 주지 않아 비교할 값이 없다.
- **크기**: ING-001 `fetch_contents`는 목록 크기가 상한을 넘으면 요청 없이 영구 실패(`SIZE_EXCEEDED`)로 적는다(ING R-08). 트리 응답도 같은 상한을 받는다.
  파일 1,569개 트리 응답은 약 0.3 MB로 추정해 기본 1 MB 안이다 `(추론)`. R-14에서 잰다.

## R-06 원본 권한 정보

- **Decision**: 저장소 조회의 `visibility`가 문자열이면 `AccessInfo(PROVIDED, (("visibility", 값),))`, 없거나 문자열이 아니면 `AccessInfo(UNKNOWN)`이다.
  값을 바꾸거나 `private` 불린에서 추론하지 않는다. 판정은 SEC-001 `judge_github_visibility`가 한다(`public`만 팀 공용).
- **Rationale**: FR-010, SEC R-05. 원값을 그대로 담아야 GitHub가 새 값을 써도 미확인으로 막힌다(명세 Edge Cases).
- **Alternatives considered**: `private: false`이면 공개로 채우기 — `internal` 저장소도 `private: true`라 구분이 흐려지고, 원값 보존(C-14)과 맞지 않는다.

## R-07 응답 분류와 한도 정보

- **Decision**: `classify`는 다음 순서로 판정하고, 나머지는 ING-001 `default_classify`에 맡긴다.

  | 응답 | 분류 |
  | --- | --- |
  | 403·429이고 `x-ratelimit-remaining: 0` | 일시적, `RATE_LIMITED` |
  | 403·429이고 `retry-after` 있음 | 일시적, `RATE_LIMITED` |
  | 그 밖의 403 | 영구, `ACCESS_DENIED` |
  | 401 | 인증 실패(ING-001 그대로) |
  | 404, 409(빈 저장소), 422(없는 `ref`) | 영구(404는 `NOT_FOUND`, 나머지는 `INVALID_RESPONSE`) |

  `rate_limit_hint`는 `x-ratelimit-remaining`을 `remaining`으로, 남은 수가 0이면 `x-ratelimit-reset`(유닉스 초)을 `retry_at`으로 읽고, `retry-after`는
  ING-001 `default_rate_limit_hint`로 읽어 늦은 쪽 시각을 쓴다. 헤더 값이 숫자가 아니면 그 헤더는 없는 것으로 본다.
- **Rationale**: FR-012~014, ING R-07의 GitHub 예외. ING-001 세션과 요청 관문이 `remaining`과 `retry_at`으로 기다림·멈춤을 이미 처리한다(`sources/limits.py`).
- **받아들인 한계**: GitHub 2차 한도 응답이 두 헤더 없이 본문 메시지로만 올 때는 영구 실패(`ACCESS_DENIED`)가 된다. 본문 문구에 기대는 분류는 하지 않는다.
  Phase 1 규모에서는 2차 한도에 닿을 가능성이 낮다 `(추론)`. 생기면 그 자료만 실패하고 다음 실행에서 다시 받는다.
- **빈 저장소**: 커밋이 하나도 없는 저장소는 커밋 조회가 409라 목록이 불완전이다. 명세 Edge Cases의 "파일이 하나도 없으면 완전"은 커밋이 있고 트리가 빈 경우로
  해석한다. 커밋이 없으면 확정할 시점이 없기 때문이다. 명세 문구 보완을 PR에서 제안한다.

## R-08 실제 전송

- **Decision**: `adapters/http.py`에 표준 라이브러리 `urllib.request` 기반 `HttpsTransport`를 둔다(런타임 의존성 추가 없음).
  - 리다이렉트를 따라가지 않는다. 3xx 응답을 그대로 돌려주고 ING-001 세션이 허용 호스트·포트를 확인해 따라간다(ING R-09).
  - 요청의 `max_bytes`보다 1바이트 더 읽어 넘치면 그만큼 자르고 `truncated=True`로 돌려준다.
  - 4xx·5xx도 예외가 아니라 응답으로 돌려준다. 시간 초과는 `TransportError("timeout")`, 연결 실패·TLS 오류는 `TransportError("connection")`이다.
  - 인증 헤더는 생성 때 받은 호스트 목록(자료원 `allowed_hosts`)으로 가는 요청에만 붙인다. 토큰은 QK-FND-001 `SecretValue`로 받아 전송 직전에만 꺼낸다.
  - 공통 헤더: `User-Agent`(GitHub 필수), `X-GitHub-Api-Version`. `Accept`는 어댑터가 요청마다 정한다.
  - TLS는 기본 인증서 검증(`ssl.create_default_context()`)을 쓴다. 요청 시간 초과는 30초다.
  - 전송은 로그를 남기지 않는다. 예외 메시지에 주소·헤더·본문을 넣지 않는다.
- **Rationale**: FR-015, FR-016. ING-001 `SourceTransport` Protocol을 그대로 구현하므로 재생 전송과 바꿔 끼울 수 있다.
- **Alternatives considered**: `httpx`·`requests` — 런타임 의존성 추가는 TASK 제외 범위다. `urllib`의 기본 리다이렉트 처리기 — 세션의 허용 호스트 검사를 건너뛴다.

## R-09 내용 해시 공용화 (FR-009, QK-ING-001 변경)

- **Decision**: `domain/source.py`에 `content_hash(body: str) -> str`(`"sha256:" + hexdigest`)를 두고, `DefaultSourceSession.finalize_content`와
  가짜 어댑터의 해시 대체값 계산이 이 함수를 부른다. GitHub 어댑터는 해시를 직접 계산하지 않는다(세션이 채운다).
- **Rationale**: 지금 같은 계산이 `sources/session.py`와 `adapters/fake.py` 두 곳에 있다. ING-001 후속 메모 1.
- **Alternatives considered**: GitHub 어댑터에 세 번째 사본 — 메모가 막으려던 갈라짐이다.

## R-10 공통 계약 시험의 기대값 주입 (FR-017, QK-ING-001 시험 변경)

- **Decision**: `tests/contract/source_adapter_contract.py`의 고정값(항목 5개, `version == "v1"`, 요청 12회, `fake.invalid` 주소, 시나리오 이름)을
  하위 클래스가 넘기는 `expected` 고정 장치(`ContractExpectations`)로 바꾼다. 원본에 없는 시나리오(GitHub는 변경 판별값이 항상 있어 내용 해시 대체가 없고,
  한 페이지라 페이지 겹침이 없다)는 시나리오 자리에 `None`을 넘기고, 그때는 같은 성질을 기본 시나리오에서 확인한다
  (모든 항목이 `VERSION`, 중복 0건). 건너뛰기(`skip`)는 쓰지 않는다(AGENTS.md 9절).
- **Rationale**: 계약 시험이 확인하는 동작은 줄이지 않고 어댑터별 값만 바꾼다. ING-001 후속 메모 2.
- **Alternatives considered**: GitHub용 계약 시험을 따로 쓰기 — 공통 계약의 뜻이 사라진다. 해당 없는 시험을 `skip` — 9절 금지.

## R-11 포함 패턴 확장자 검증 (FR-019)

- **Decision**: 포함 패턴의 마지막 경로 조각에 점이 있으면 마지막 점 뒤를 확장자로 본다. 확장자가 영숫자만이면 SEC-001 `FILE_EXTENSIONS`(대소문자 무시)에
  있어야 하고, 없으면 `UNKNOWN_EXTENSION`이다. 확장자 자리에 글롭 문자(`*`, `?`, `[`)가 있으면 판정할 수 없으므로 같은 오류다. 마지막 조각에 점이 없는
  패턴(`docs/**`, `README*`)은 검사하지 않는다. 그 패턴으로 들어온 목록 밖 확장자 파일은 SEC-001이 막고 기록한다(SEC R-07).
- **위치**: 새 모듈 `sources/scope_review.py`. 결과는 ING-001 `ConfigIssue`(자료원, 필드, 코드)로 내고, `qk-index sources check`와 `run`이 자료원 설정 오류와 함께 보인다.
  ING-001 `sources/config.py`와 SEC-001 `security/`는 고치지 않는다.
- **Rationale**: SEC R-07. 확장자 목록은 SEC-001 주소 정책의 일부(`domain/redact.py`)라 그 상수를 그대로 쓴다.
- **Alternatives considered**: `load_sources`에 넣기 — 종류와 무관한 ING-001 검증에 SEC-001 정책이 섞인다. `security check`에만 넣기 — `sources check`로 확인하는
  운영 흐름(ING-001 contracts/cli.md)에서 빠진다.

## R-12 개인 정보 확인 기록 (FR-020, 2026-10-20 사용자 결정 안 A)

- **Decision**: 기록은 `config/source_reviews/<자료원 이름>.toml` 한 파일이다. 형식은 [contracts/source-reviews.md](contracts/source-reviews.md).
  `qk-index sources check`와 `run`은 활성 자료원마다 다음을 확인하고 어긋나면 `ConfigIssue`를 낸다. 원본은 부르지 않는다.
  - 파일이 있고 TOML로 읽힌다(`REVIEW_MISSING`, `REVIEW_INVALID`).
  - 필수 항목이 있다: 자료원 이름, 확인 날짜, 확인한 사람의 역할, 확인 방법, 결과, 수집 범위(`REVIEW_INVALID`).
  - 기록의 자료원 이름과 파일 이름이 같다(`REVIEW_INVALID`).
  - 기록의 수집 범위(저장소, `ref`, 포함·제외 패턴)가 현재 자료원 설정과 같다. 패턴은 순서까지 같아야 한다(`REVIEW_SCOPE_MISMATCH`).
  - 제외로 옮긴 경로가 모두 현재 제외 패턴에 있다(`REVIEW_SCOPE_MISMATCH`).
  - 결과가 `개인 정보 없음` 또는 `개인 정보 경로 제외함` 중 하나다(`REVIEW_INVALID`).
- 비활성 자료원은 검사하지 않는다. 그래서 구현 단계는 첫 자료원을 비활성으로 등록하고, 사람이 확인한 뒤 기록을 쓰고 활성으로 바꾼다(R-13).
  에이전트는 확인 기록을 대신 만들지 않는다. 기록은 사람이 확인한 사실의 증빙이기 때문이다.
- **Rationale**: 범위를 바꾸고 기록을 빠뜨리면 수집 전에 막힌다(US4 시나리오 2, SC-008). 패턴 순서까지 같게 하면 비교 규칙이 단순하고, 순서만 바꾸는 변경도
  기록을 고치게 되어 리뷰에 드러난다.
- **Alternatives considered**: 기록을 `config/sources.toml`의 항목으로 넣기 — ING-001 설정 형식과 모르는 키 검사를 바꿔야 한다. 범위 해시만 적기 — 사람이 기록을 읽어
  무엇을 확인했는지 알 수 없다.
- **개인 식별 정보**: 확인한 사람은 역할(예: "백엔드 리뷰어")로만 적는다. 이름·연락처가 들어가지 않았는지는 PR 리뷰에서 본다. 자동 검사는 하지 않는다(SEC-001 FR-024와 같은 선).

## R-13 첫 자료원 등록 (FR-018)

- **Decision**: `config/sources.toml`에 다음을 **비활성**(`enabled = false`)으로 등록한다. 포함 패턴은 인벤토리 1.2절 "포함" 범주를 옮긴 초안이고,
  사람 확인과 R-14 측정에서 고칠 수 있다.

  ```toml
  [[source]]
  name = "dnd-backend-docs"
  kind = "github_repo_files"
  enabled = false
  auth = "GITHUB_API_TOKEN"
  [source.scope]
  repo = "dnd-side-project/dnd-15th-2-backend"
  ref = "main"
  include = [
    "README.md", "AGENTS.md", "CLAUDE.md", "CODEX.md", "TASK.md",
    "docs/adr/**/*.md", "docs/product/**/*.md", "docs/harness/**/*.md",
    "docs/api-response.md", "docs/error-codes.md", "docs/filtering-production-gate.md",
    "docs/push-production-setup.md", "docs/api/OPENAPI_WRITING_GUIDE.md",
    "docs/superpowers/plans/**/*.md", "docs/superpowers/specs/**/*.md",
    "infra/**/*.md", "**/AGENTS.md", ".github/PULL_REQUEST_TEMPLATE.md", "scripts/repo-map/README.md",
  ]
  exclude = [".claude/**", ".agents/**", ".codex/**", "agents/**", "templates/**", "docs/experiments/**"]
  ```

  한도·재시도는 ING-001 기본값을 쓴다. R-14 측정 뒤 FR-023으로 다시 본다.
- **Rationale**: C-04. "결정 필요" 범주(테스트 계획·결과, 설계 보고서, 에이전트 설정)는 넣지 않는다. `**/AGENTS.md`가 에이전트 설정 디렉터리 안의 파일까지 잡지 않도록
  그 디렉터리를 제외한다. 겹치면 제외가 이긴다(ING-001 FR-012).
- **활성화 절차(사람)**: 1) 범위 안 파일을 살펴 개인 정보를 확인한다. 2) `config/source_reviews/dnd-backend-docs.toml`을 쓴다. 3) `enabled = true`로 바꾼다.
  4) `qk-index sources check`가 통과하는지 본다. 5) R-14 측정을 실행한다. 이 다섯 단계는 한 PR에서 사람 리뷰를 받는다.

## R-14 첫 실제 수집 측정 (FR-022, FR-023)

- **Decision**: 측정 명령 `qk-dev source measure --name <자료원>`을 둔다(`devtools/measure.py`). 자료원 설정·확인 기록 검사를 통과한 활성 자료원 하나를
  실제 전송으로 `screen_source`(SEC-001)까지 돌리고, 저장·임베딩 없이 측정값만 낸다. 출력 항목은 [contracts/cli.md](contracts/cli.md)에 있다.
  사람이 실행해 결과를 `docs/sdd/research/github-source-measurement.md`에 옮기고, 한도값 판단(FR-023)을 같은 문서에 적는다.
  같은 측정 함수를 부르는 외부 호출 시험 하나(`tests/external/test_github_repo_source.py`, `@pytest.mark.external`)가 요청 수 ≤ 실행당 한도, 목록 완전,
  판정 실패 0건을 확인한다.
- **Rationale**: FR-022는 사람이 실행하는 1회 측정이다. 명령으로 두면 기본 검증과 CI에서 실제 원본을 부르지 않고(FR-016), 같은 절차를 다음 자료원에도 쓴다.
  측정 기록에 경로가 나와도 공개 저장소 경로이고, 판정 기록은 SEC-001 가림 규칙(FR-023)을 거친다.
- **Alternatives considered**: 외부 호출 시험만 두기 — 시험 출력은 기록 형식이 아니고 실행할 때마다 모양이 다르다. QK-SYN-001의 실행 명령을 기다리기 — 첫 실제 색인
  전에 측정해야 한다(FR-022).
- **비용**: GitHub 호출 약 84회(토큰 한도 시간당 5,000회 안). 임베딩 0 Neurons.

## R-15 시험 자료

- **Decision**: 재생 응답은 `tests/fixtures/responses/github/<시나리오>.json`에 둔다(`_meta.source_api`는 `github.rest`). 내용은 합성 Markdown이고 실제 대상
  저장소 내용을 옮기지 않는다. blob SHA는 합성 내용으로 계산한 실제 git blob SHA를 넣는다(시험이 R-05 검증을 통과해야 하므로). UTF-8이 아닌 바이트처럼
  재생 형식(JSON 문자열)으로 쓸 수 없는 응답은 시험 안의 작은 전송 대역으로 만든다. ING-001 `ReplayTransport`는 고치지 않는다.
- 실제 전송 시험은 표준 라이브러리 `http.server`를 쓰지 않는다. 로컬 HTTPS 인증서가 필요해 시험이 무거워진다. 대신 `urllib` 처리기 경계를 대역으로 바꿔
  리다이렉트 미추종, 크기 자르기, 오류 변환, 인증 헤더 호스트 제한을 확인한다.

## R-16 결정 기록 필요 여부 (AGENTS.md 3.1)

- **사실**: AGENTS.md 3.1은 "새 자료원이나 새 외부 모델을 추가할 때" 데이터 처리 정책을 확인하고 결정 기록을 남기라고 한다. `github_repo_files` 종류는 QK-ING-001에서
  등록됐지만, 그 종류의 결정 기록은 `docs/sdd/decisions/`에 없다. 독립 검토도 "실제 자료원 등록·수집 전 데이터 처리 결정 기록"을 후속 확인 위험으로 적었다.
- **Decision**: 첫 자료원 활성화(R-13 3단계) 전에 결정 기록이 필요한지와 그 ID를 사람이 정한다. 필요하면 활성화 PR에 `templates/decision-record.md`로 쓴다.
  내용 후보: 공개 저장소 읽기 전용, 본문은 QK-EMB-001 임베딩 공급자(ADR-002)로만 나감, 보존은 QK-STO-001 저장과 같음.

## 이 계획에서 하지 않는 것

- 이전 실행과의 비교, 삭제 반영, 주기 실행, 수집 결과 저장(QK-SYN-001). 종류 이름과 어댑터를 잇는 일반 등록부도 QK-SYN-001이 진입점에서 만든다.
  이 계획은 측정 명령에서만 GitHub 어댑터를 직접 고른다.
- 웹훅, GitHub App 인증, 비공개 저장소.
