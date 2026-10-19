# Research: QK-SEC-001 색인 제외 경로·비밀값 차단·접근 범위 판정

**Date**: 2026-10-20 | **Spec**: [spec.md](spec.md) | **Plan**: [plan.md](plan.md)

명세의 확인 필요 표시는 없다. 아래는 계획을 세우며 정한 설계 결정이다. 근거로 읽은 코드는 PR #35 브랜치 HEAD(`baa59b8`) 기준이다.

## R-01 필터 위치: 목록 조회와 본문 조회 사이

- **Decision**: 보안 필터를 두 단계로 나눈다. 목록 단계(`screen_items`)는 ING-001 `list_all()`이 돌려준 `SourceItem`을 받아 경로 제외, 접근 범위,
  메타데이터 안전성(원본 식별자·위치·제목·원본 링크의 비밀값, 원본 식별자의 주소)을 판정한다. 본문 단계(`screen_contents`)는 `fetch_contents()`가 받은 `SourceContent`의
  본문·제목·위치를 검사한다. 두 단계를 잇는 조립 함수 `screen_source()`를 `security` 패키지에 두고, QK-SYN-001은 이 함수를 부른다.
- **Rationale**: FR-002 "추가 본문 조회 0건"은 목록 단계에서 빠진 자료를 `fetch_contents()`에 넘기지 않으면 지켜진다. ING-001 `collect.py`는
  본문을 받은 자료의 `source_id`를 로그에 남기므로(`sources/collect.py`의 `logger.info`), 식별자·위치·제목에 든 비밀값은 본문 조회 전에 막아야
  ING-001 로그로 새지 않는다(FR-023, SC-005). ING-001은 본문을 받은 자료의 `source_id`를 `collect.py` 로그와 `FetchResult.to_dict()`에 그대로 남기고
  이 둘은 가릴 수 없다. 그래서 `source_id`에서 비밀값이나 주소(R-07의 필드별 규칙으로 판정, 맨 호스트 포함)가 나오면 본문 조회 전에 막는다
  (`SECRET_BLOCKED`, `rule=identifier-address` 또는 비밀값 규칙 이름). 위치·제목·링크의 주소는 막지 않고 이 명세의 기록에서 가린다. ING-001은 이 필드들을
  로그와 요약에 남기지 않는다(2026-10-20 사용자 결정, 설계 리뷰 1번. #35는 고치지 않는다). 조립 함수가 있어야 SC-003·004를 재생 전송의 요청 기록으로
  시험할 수 있다. 목록 단계 이후 요청만 세려면 시험은 `list_all()` 반환 시점의 요청 수를 기준으로 증가분을 본다.
- **Alternatives considered**: (a) `fetch_contents()` 안에 필터를 넣기 — ING-001 코드를 바꿔야 하고 TASK.md 제외 범위다. (b) 본문을 받은 뒤 한 번에
  판정 — 추가 본문 조회 0건과 식별자 로그 비노출을 지킬 수 없다. (c) 조립을 QK-SYN-001에 맡기기 — 이 명세의 SC를 시험할 곳이 없어진다.

## R-02 비밀값 규칙을 커밋 검사와 한 벌로

- **Decision**: 규칙을 `src/qello_knowledge/domain/secret_rules.py`(표준 라이브러리만)로 옮기고, `scripts/preflight.py`는 이 파일을
  `importlib.util.spec_from_file_location`으로 경로에서 직접 불러 같은 `RULES`를 쓴다. 패키지 설치나 `qello_knowledge` 패키지 가져오기에 기대지 않는다.
  모듈은 Python 3.12에서도 돌게 쓴다(3.13 전용 문법·함수 금지).
- **Rationale**: CI `secrets` job은 `uv sync` 없이 시스템 `python3`(ubuntu-latest, 3.12)로 `python3 scripts/preflight.py`를 돈다. 패키지 경로를
  `sys.path`에 넣는 방식은 `qello_knowledge/__init__.py`와 하위 패키지 초기화에 기대게 된다. 파일 하나를 경로로 불러오면 그 위험이 없다.
  `domain`에 두면 경계 시험(`tests/unit/test_boundaries.py`)이 표준 라이브러리만 쓰는지 검사해 준다.
- **Alternatives considered**: (a) TOML 데이터 파일 — 정규식 이스케이프를 TOML 문자열로 옮기면 읽기 어렵고, 규칙 이름·플래그를 따로 다뤄야 한다.
  (b) 두 곳에 같은 목록을 복사하고 동일성 시험 — FR-009 "갈라지지 않게"를 시험으로만 지키게 된다.
- **`--staged`**: 규칙 모듈도 staged 내용으로 검사해야 한다(설계 리뷰 4번). `--staged`면 `git show :src/qello_knowledge/domain/secret_rules.py`로 index의
  소스를 읽어 새 모듈 객체에 `exec`하고, 그 밖에는 작업 트리 파일을 경로로 불러온다. index에 규칙 파일이 없으면 검사 실패다.
  그래서 규칙에 staged되지 않은 변경이 있어도 커밋될 규칙으로 검사한다.
- **시험**: (a) `ast.parse(source, feature_version=(3, 12))`로 3.12 문법 확인, (b) `python3 -I scripts/preflight.py`(사용자 site-packages와
  `PYTHONPATH` 무시)로 패키지 없이 도는지 확인, (c) 임시 git 저장소에서 작업 트리 규칙과 index 규칙을 다르게 두고 `--staged`가 index 규칙을 쓰는지 확인.
  실제 3.12 실행은 CI `secrets` job이 확인한다.
- `preflight.py` 수정은 하네스 스크립트 변경이라 PR에서 따로 확인받는다(plan.md 사람 확인).

## R-03 반드시 잡을 토큰 형식 (FR-009)

- **Decision**: 현재 규칙 12개를 유지하되 이름 규칙 두 개를 넓히고, 새 규칙 4개를 더해 16개로 만든다. 정확한 정규식은 구현에서 합성값 시험으로 확정한다.

| 규칙 이름 | 대상 | 형식 근거 |
| --- | --- | --- |
| `github-fine-grained-token` | GitHub 세분화 토큰 | `github_pat_` 접두사 `(일반 설명)` |
| `cloudflare-account-token` | Cloudflare 계정 소유 토큰 | `cfat_` 접두사(`tokens.md` T-01) |
| `discord-bot-token` | Discord 봇 토큰 | 점으로 나뉜 세 부분(사용자 ID base64, 시각, HMAC) `(일반 설명)` |
| `clickup-token` | ClickUp 개인 토큰 | `pk_` + 숫자 + `_` + 영숫자(`tokens.md` T-01) |
| `assigned-secret` (확장) | 따옴표로 할당한 `*token*`, `*secret*` 이름(`GITHUB_TOKEN = "…"`, `service_secret: '…'`) | 현재 `SECRET_NAME`에 일반 `token`·`secret`이 없다(설계 리뷰 5번) |
| `env-assigned-secret` (확장) | `*_TOKEN`, `*_BOT_TOKEN`, `*_SECRET` 이름에 따옴표 있거나 없는 값 | 현재 규칙이 `BOT_TOKEN`으로 끝나는 이름과 따옴표 값을 놓친다(T-01, 설계 리뷰 5번) |

- **Rationale**: `tokens.md` T-01이 커밋 검사 누락을 기록했고, 1차 검토가 합성값으로 세 종류가 걸리지 않음을 재현했다. 형식이 고정되지 않은
  Cloudflare 레거시 토큰(접두사 없음)은 길이 규칙 없이는 잡을 수 없다. ING-001 재검토에서 길이 규칙을 오탐 때문에 뺐으므로(#34 TASK.md)
  이름 규칙(`CLOUDFLARE_API_TOKEN=...`)으로만 잡는다.
- **시험**: `REQUIRED_KINDS`마다 합성값 1건 이상, 이름 규칙은 접미사(`TOKEN`, `BOT_TOKEN`, `SECRET`, `PASSWORD`, `API_KEY`)마다 따옴표 할당·env 할당 두 형태로
  시험한다. 자리표시(`${…}`, `<…>`, `example`, `changeme`)는 걸리지 않음도 같이 본다. 넓힌 이름 규칙이 이 저장소 파일에 걸리면 같은 PR에서
  `preflight_allowlist.txt`에 사유와 함께 넣는다.
- **Alternatives considered**: 엔트로피·길이 기반 탐지 — 해시, 커밋 SHA, UUID가 많은 저장소 문서에서 오탐이 크다.

## R-04 기본 제외 규칙과 경로 맞춤 (FR-006~008)

- **Decision**: `src/qello_knowledge/domain/exclusions.py`에 (범주, 패턴) 목록을 둔다. 경로는 `posixpath.normpath`로 정리한 뒤
  `PurePosixPath.full_match(pattern, case_sensitive=False)`로 맞춘다. 정리한 경로가 `..`로 시작하거나 절대 경로면 `path-invalid` 규칙으로 뺀다.
  예시 파일(`*.example`, `*.sample`, `*.template`, `.env.example` 등)은 `.env` 패턴과 `*.tfvars` 패턴에서만 빼고 비밀값 검사로 넘긴다.
  `*.tfstate*`와 `.terraform/**`, 그 밖의 범주는 예시 이름이어도 계속 뺀다(설계 리뷰 6번).

| 범주 | 패턴(초안) |
| --- | --- |
| `env-file` | `**/.env`, `**/.env.*`(예시 제외) |
| `private-key-file` | `**/*.pem`, `**/*.key`, `**/*.p12`, `**/*.pfx`, `**/*.jks`, `**/*.keystore`, `**/id_rsa*`, `**/id_ecdsa*`, `**/id_ed25519*` |
| `secret-dir` | `**/secrets/**`, `**/.secrets/**` |
| `infra-state` | `**/*.tfstate`, `**/*.tfstate.*`, `**/*.tfvars`(예시 제외), `**/.terraform/**` |
| `build-output` | `**/node_modules/**`, `**/build/**`, `**/dist/**`, `**/target/**`, `**/.gradle/**`, `**/.venv/**`, `**/__pycache__/**` |
| `vcs-internal` | `**/.git/**` |

- **Rationale**: 0.2 인벤토리가 백엔드 저장소의 `.env.example`, `*.tfvars.example`을 비밀값 검사 대상으로 꼽았다(빼면 안 된다). `preflight.py`의
  `SKIP_PARTS`, `tracked_environment_files()`와 같은 범주다. 대소문자 무시는 `.ENV`처럼 표기만 다른 경로를 막는다(FR-008).
  ING-001 `in_scope()`는 대소문자를 구분하지만, 기본 제외는 더 엄격한 쪽(무시)이 맞다.
- **Alternatives considered**: 자료원 설정의 `scope.exclude`에 기본값으로 넣기 — 설정 파일에서 지울 수 있어 FR-007(해제 불가)을 어긴다.
- **FR-007 해제 차단**: 자료원 설정에는 기본 제외를 끄는 키가 없고, 모르는 키는 ING-001 검증이 `UNKNOWN_KEY`로 막는다. 이 동작을 시험으로 고정한다.
- **위험**: `**/build/**`가 문서 디렉터리 이름과 겹칠 수 있다. 판정 기록(US4)으로 찾고, 필요하면 범주를 좁힌다.

## R-05 접근 판정 규칙과 공개 원본 링크 호스트

- **Decision**: `security/kinds.py`에 자료원 종류별 보안 정책 `KindSecurityPolicy(access_rule, public_link_hosts)`를 등록한다. ING-001
  `sources/kinds.py`는 고치지 않는다. 필터는 이 등록부를 인자로 받고(기본값은 모듈 등록부), 등록되지 않은 종류는 `UNKNOWN`이다.

| 종류 | 접근 규칙 | 공개 원본 링크 호스트 |
| --- | --- | --- |
| `github_repo_files` | `raw`가 정확히 `(("visibility", "public"),)`이면 `TEAM`. 그 밖(`private`·`internal`·키 중복·모르는 키·값)은 `UNKNOWN` | `github.com` |
| `fake` | `visibility`: `public`→`TEAM`, `restricted`→`RESTRICTED`, 그 밖→`UNKNOWN` | `fake.invalid` |

- **Rationale**: FR-015는 규칙 추가 때 공통 동작이 바뀌지 않기를 요구한다(SC-006). 등록부를 인자로 받으면 두 번째 가짜 종류 시험이 등록부만
  넘겨 공통 코드 변경 0줄을 보일 수 있다(ING-001 SC-001과 같은 방식). 가짜 자료원 응답 샘플이 이미 `"access": {"visibility": "public"}`을 쓴다.
  GitHub 저장소 공개 범위를 `visibility` 키로 담는 일은 QK-ING-002가 이 규칙에 맞춘다.
- **Alternatives considered**: ING-001 `SourceKindSpec`에 필드 추가 — #35 리뷰 중인 코드를 바꾸게 된다(TASK.md 제외 범위).
- **`RESTRICTED`**: GitHub 규칙은 `RESTRICTED`를 만들지 않는다(FR-017은 비공개를 미확인으로 둔다). 원본이 제한을 확정해 주는 자료원(ClickUp 등)을 위해
  값만 둔다. 판정 결과는 미확인과 같다(FR-018).

## R-06 오탐 예외 목록은 커밋 검사 예외와 분리

- **Decision**: 색인 필터 예외는 새 파일 `config/security_exceptions.toml`에 `[[exception]]` 표(`source`, `path`, `rule`, `reason`)로 둔다.
  `scripts/preflight_allowlist.txt`와 합치지 않는다.
- **Rationale**: 커밋 검사 예외는 이 저장소 파일이 대상이고, 색인 예외는 수집 대상 저장소의 파일이 대상이라 자료원 구분이 필요하다(FR-012).
  형식을 하나로 합치면 커밋 검사에도 자료원 열이 생겨 하네스 형식이 바뀐다. 명세 Assumptions의 조건(합치더라도 자료원 구분 유지)을 분리로 만족한다.
- **검증**: 모든 필드가 비어 있지 않은 문자열, `rule`은 등록된 규칙 이름, `source`는 자료원 설정에 있는 이름, 같은 (source, path, rule) 중복 금지.
  `path`에 와일드카드를 허용하지 않는다(경로 없이 규칙 전체를 끄는 것과 같아진다). 오류가 하나라도 있으면 수집 전에 멈춘다.

## R-07 기록 출력 규칙 (FR-019, FR-023)

- **Decision**: `security/redact.py`의 `safe_text(value, field_kind, context)`가 모든 출력 필드를 가린다. `field_kind`는 `LINK`·`PATH`·`TEXT`이고,
  `context`는 `OutputContext(public_link_hosts, source_id_is_path, address_policy)`다. 필드와 종류의 대응은 data-model.md `OutputContext`에 고정한다. 순서는 (1) 비밀값 규칙에 걸리면 필드 전체를
  `[가림:<규칙 이름>]`으로, (2) 주소 패턴(`scheme://…`, IPv4·IPv6, `host:port`)은 원본 링크 필드에서 공개 원본 링크 호스트의 `https` 주소만 남기고
  나머지는 `[가림:address]`로 바꾼다. (3) 맨 호스트 이름은 필드 종류별로 판정한다(2026-10-20 사용자 결정, 설계 재리뷰 방안 A).

| 필드 종류 | 해당 필드 | 점으로 이어진 이름(`a.b`, `x.y.z`) |
| --- | --- | --- |
| 링크 | `url` | (2)대로 공개 원본 링크 호스트의 `https` 주소만 남긴다 |
| 경로 | `location`, 자료원 종류가 `source_id_is_path=True`로 등록한 종류의 `source_id` | 정규화한 경로를 `/`로 나눈다. 마지막 부분(파일 이름)이 `<이름>.<확장자>`이고 확장자가 `FILE_EXTENSIONS`에 있으면 파일 이름으로 보고 남긴다. 디렉터리 부분과 확장자가 목록에 없는 파일 이름은 글 필드와 같이 판정한다 |
| 글 | `title`, 경로가 아닌 `source_id`, 원본 권한 원값의 키·값, 그 밖의 문자열 | 모든 부분이 숫자(버전 `1.2.3`)일 때만 남기고, 끝부분이 무엇이든(`md`, `py` 포함) 가린다 |

  `FILE_EXTENSIONS` 예: `md`, `mdx`, `txt`, `py`, `java`, `kt`, `kts`, `ts`, `js`, `json`, `yml`, `yaml`, `toml`, `sql`, `tf`, `hcl`, `xml`, `gradle`,
  `properties`, `sh`, `csv`, `html`, `css`, `png`, `svg`. 대소문자는 무시한다.
  원본 권한 원값은 키와 값을 각각 같은 함수로 거른다. `SecurityVerdict.to_dict(context)`와 로그는 이 함수를 거친 값만 쓴다. 목록 단계 5번의
  식별자 주소 판정도 같은 함수와 같은 `context`를 쓴다. 그래서 판정과 기록의 주소 정책이 갈라지지 않는다(설계 재리뷰 2차 P2).
- **Rationale**: 1차·2차 검토가 지적한 대로 기록 허용 기준은 요청 허용 호스트(`allowed_hosts`)와 다르다. 일찍 빠진 자료(경로 제외·접근 보류·판정 실패)도
  같은 함수를 거치게 해 판정 경로와 상관없이 기록 규칙이 같다.
- **명세 해석**: 확장자와 겹치는 호스트(`<이름>.md`, `md`·`py`·`sh`는 국가 도메인이기도 하다)는 글자만으로 파일 이름과 구분할 수 없다(설계 재리뷰 1번).
  그래서 FR-023의 "주소"를 "경로 필드의 파일 이름 부분은 주소가 아니다"로 해석한다. 근거는 C-07(모든 청크는 원본 위치로 되돌아갈 수 있어야 한다)이다.
  파일 이름은 원본 자료의 위치이고, 이를 가리면 판정 기록으로 원본을 찾을 수 없다. 같은 문자열이 제목·권한 원값·경로 아닌 식별자·디렉터리 부분에
  있으면 끝부분과 상관없이 가리거나(기록) 막는다(`source_id`). 이 해석은 명세 문구에 없으므로 plan.md 사람 확인 항목에 명세 보완 제안으로 남긴다.
- **오탐 방향**: 글 필드에서는 점이 든 일반 문자열(`README.md`라는 제목)도 가린다. 기록이 덜 읽히는 쪽으로만 틀린다. 경로 필드에서는 확장자 목록에 없는
  파일 이름(`notes.adoc`)이 가려지고, 그것이 경로형 `source_id`면 자료가 막힌다(R-01). 그래서 QK-ING-002가 포함 패턴을 정할 때 확장자를 목록과 대조하고,
  GitHub `source_id`를 저장소 안 경로로 정하는지 확인한다. 막힌 사례는 `rule=identifier-address`로 판정 기록에 남아 검토할 수 있다.

## R-08 보안 규칙 버전 (FR-022)

- **Decision**: 판정을 바꿀 수 있는 입력 전체를 정해진 순서의 JSON으로 만들고 SHA-256 앞 12자리를 붙여 `sec-<12자리>`로 쓴다. 입력은 비밀값 규칙(이름·패턴·플래그),
  기본 제외(범주·패턴·예시 접미사), 예외 목록(정렬한 항목), 주소 탐지 정책(정규식 소스, 정렬한 `FILE_EXTENSIONS`, `ADDRESS_POLICY_VERSION`),
  등록된 종류별 정책(종류, 접근 규칙 이름, `public_link_hosts`, `source_id_is_path`)이다(설계 재리뷰 2번).
- **시험**: 위 입력 하나만 바꾼 정책마다 버전이 달라지는지 본다. 특히 `FILE_EXTENSIONS`에 확장자 하나를 더하거나 `source_id_is_path`만 바꿔도 버전이 바뀐다.
- **Rationale**: 사람이 버전을 올리는 것을 잊어도 바뀐 내용이 버전에 반영된다. 같은 내용이면 같은 버전이라 재현된다(C-07).

## R-09 판정 실패는 막는 쪽으로 (FR-004)

- **Decision**: 자료 하나의 판정을 `try`로 감싸 예외가 나면 `ERROR` 판정으로 기록하고 그 자료를 통과시키지 않는다. 오류 기록에는 예외 클래스 이름만
  남기고 메시지는 남기지 않는다(FR-023). 시험은 접근 규칙이 예외를 내는 가짜 정책을 넘겨 확인한다(SC-007).

## R-10 전송 직전 검사 API (FR-013)

- **Decision**: `security/send_gate.py`의 `check_outgoing(pieces, policy) -> SendCheck`. `OutgoingPiece(text, origin)`에서 `origin`은
  `(source_name, path)` 또는 `None`이다. 예외는 `origin`이 있는 조각에만 그 (자료원, 경로) 예외를 적용한다. 하나라도 걸리면 `SendCheck.allowed=False`와
  (조각 번호, 규칙 이름, 줄 번호) 목록을 돌려준다. 호출하는 쪽(QK-EMB-001·GEN-001)은 `allowed`가 거짓이면 보내지 않는다.
- **Rationale**: 출처가 섞인 문자열 하나를 받으면 어느 예외를 적용할지 정할 수 없다(1차 검토 5번). 조각 단위면 SC-009를 그대로 시험할 수 있다.

## R-11 막힌 본문은 다음 단계로 넘기지 않는다

- **Decision**: `screen_source()`는 ING-001 `FetchResult`를 `dataclasses.replace(result, contents=())`로 본문을 비운 사본만 결과에 담고,
  통과한 본문은 `ScreenResult.passed`에만 담는다.
- **Rationale**: `FetchResult.contents`에는 비밀값 차단된 본문도 들어 있다. 그대로 넘기면 QK-SYN-001이 실수로 차단된 본문을 쓸 수 있다(FR-011).

## R-11a 목록 상태를 보존한다

- **Decision**: `screen_source()`는 `fetch_contents()`에 튜플이 아니라 `dataclasses.replace(listing, items=passed_items)`를 넘긴다.
- **Rationale**: `fetch_contents()`는 튜플을 받으면 `Listing(tuple(items))`를 새로 만들어 `complete=True`, `stop=None`이 된다(`sources/collect.py`).
  목록 조회가 중간에 실패했는데 완료로 바뀌면 QK-SYN-001이 빠진 자료를 원본 삭제로 오해한다(설계 리뷰 2번).
- **시험**: 페이지 조회 실패 응답 샘플로 `ScreenResult.fetch.listing_complete`가 거짓으로 남는지, 멈춤 정보가 남는지 본다.

## R-11b 본문 조회 실패·미시도 자료도 판정 기록을 남긴다

- **Decision**: 목록 단계를 통과했지만 본문을 받지 못한 자료는 `ERROR`(판정 실패), `stage=FETCH`, `error_type=fetch:<ItemStatus>:<FailureType 또는 none>`으로
  기록한다(예: `fetch:PERMANENT_FAILED:NOT_FOUND`, `fetch:SKIPPED:none`). ING-001 `FetchResult.items`의 `ItemOutcome`에서 만든다.
- **Rationale**: FR-003은 자료마다 다섯 결과 중 하나를, FR-020은 자료별 판정 기록을 요구한다. 보안 판정을 끝내지 못했으므로 "판정 실패"가 맞다
  (설계 리뷰 7번). 명세의 다섯 결과를 늘리지 않는다.
- **시험**: 목록에 나온 자료 수 = 판정 기록 수 = 요약의 결과별 합. 영구 실패·재시도 소진·멈춤으로 건너뜀이 섞인 시나리오로 본다.

## R-12 시험 자료에 실제 같은 비밀값을 커밋하지 않는다

- **Decision**: 비밀값을 심은 시험 자료는 시험 코드에서 문자열을 이어 붙여 만든다(예: `"gh" + "p_" + "A" * 36`). 응답 샘플 JSON에는 비밀값 자리에
  `{{SECRET:<종류>}}` 자리표시를 두고 시험 도우미가 실행 중에 바꾼다.
- **Rationale**: 시험 파일에 토큰 형식 값이 그대로 있으면 `preflight.py`가 실패하고, 예외 목록에 시험 파일을 넣으면 그 파일의 실제 유출을 놓친다.

## R-13 개인 정보 확인 절차 (FR-024)

- **Decision**: 이 명세에서 개인 정보용 코드는 만들지 않는다. 필터는 자료원 설정의 `scope.exclude`(ING-001)를 기본 제외와 함께 지키고, 이를 시험한다
  (SC-003 뒷부분). 범위를 넓힐 때의 사람 확인 기록 형식과 위치는 QK-ING-002가 정한다.
- **Rationale**: 2026-10-19 사용자 결정(명세 1차 검토 반영).

## R-14 성능 (SC-008)

- **Decision**: 합성 자료 81개, 총 1.1 MB로 `screen_items`·`screen_contents`를 도는 시험을 두고 60초 상한을 단언한다. 정규식은 모듈을 불러올 때 한 번만
  컴파일한다.
- **Rationale**: 규칙 16개 × 약 3만 줄 수준이라 1초 안팎으로 예상된다 `(추론)`. 상한은 명세의 1분을 그대로 쓴다.

## R-15 공수 다시 잡기

- **Decision**: 로드맵 크기 S(약 1인일)를 M(약 2~3인일)로 보는 게 맞다 `(추론)`. 근거는 새 모듈 7개(규칙·제외·정책·가림·필터·전송 검사·CLI),
  `preflight.py` 수정, 시험 약 12개 파일이다. 로드맵 수정은 사람 승인 대상이라 plan.md 사람 확인 항목으로 남긴다.
