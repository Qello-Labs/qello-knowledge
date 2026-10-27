# Task Contract: #82 출력 가림 IPv6 후보 검사의 긴 16진·콜론 입력 성능 수정

> Generated at: `2026-10-28`
>
> 이 파일은 현재 작업 브랜치의 계약이다. 저장소 공통 정책은 `AGENTS.md`를 따른다.

## Work gate

- Jira 이슈: 해당 없음: 2026-10-28 사용자 결정으로 Jira 없이 진행하는 예외 작업
- 기능명세서 ID / 링크: `QK-SEC-001` / `specs/QK-SEC-001-security-filter/`(주소 가림 구현 성능 결함 수정. 명세 요구사항은 바꾸지 않는다)
- 팀 스프린트 ID: 해당 없음: Jira 없이 진행하는 예외 작업
- GitHub Issue: `#82`
- Branch: `fix/gh-82-redact-ipv6-performance`
- Base branch: `main`. 2026-10-28 `origin/main` `580f83e`(#83 병합)에서 분기했다

## Objective

- IPv6 후보 검사가 긴 16진·콜론 입력에서 길이에 비례하되 작은 상수 시간으로 끝나게 한다.
- 가림 결과와 판정은 바꾸지 않는다. 옛 `_mask_ipv6`와 출력이 글자 그대로 같다는 것을 비교로 보인다.

## Scope

- `src/qello_knowledge/domain/redact.py`
  - `_mask_ipv6`: 위치마다 `ipaddress`를 부르는 대신 `ipaddress`가 받는 IPv6 표기와 같은 문법의 정규식(`IPV6`)으로 후보를 찾는다.
    왼쪽부터 가장 긴 유효 후보를 가리는 규칙은 그대로다(구현 방식은 아래 Decisions)
  - `IP_RUN` 등 `AddressPolicy.patterns`의 패턴 문자열과 `ADDRESS_POLICY_VERSION`(`address-v6`)은 그대로 둔다(보안 규칙 버전 `sec-91a57f4542e8` 유지)
- `tests/unit/security/test_redact.py`: 16진·콜론 반복 입력(`fffff:`, `f:f.`, `a.a.a.a:99999`, `::` 등) 10만 자 성능 시험을
  `test_long_dotted_runs_without_a_scheme_are_cheap`와 같은 꼴로 더한다. 기존 시험 기대값은 바꾸지 않는다
- `TASK.md`

## Explicit exclusions

- 가림·판정 결과 변경. 출력이 달라져야만 하는 경우가 나오면 멈추고 사용자에게 알린다(그때는 버전을 올리고 `identifier-address` 색인 제외 영향을 확인한다)
- 비밀값 규칙(`secret_rules.py`), 스킴·IPv4·`host:port`·점 이름 가림, 확장자 예외, 필드 종류 판정 변경. QK-SEC-001 명세 문서 변경
- 운영 반영 실행(동기화 수동 실행, 운영 DB 쓰기), 운영 접속
- `AGENTS.md`, `CLAUDE.md`, `.claude/**` 수정. 원본 자료원 쓰기
- 공유 DB 초기화, 인덱스 전체 삭제, 유료 과금 설정 변경은 별도 승인 없이 하지 않는다.
- 비밀값, 토큰, `.env` 값, 비공개 원문, 실제 주소·도메인은 기록하지 않는다. 시험·비교에는 합성 주소(`192.0.2.x`, `2001:db8::/32`)만 쓴다.

## Data and cost impact

- 새로 읽는 자료원: 해당 없음
- 외부 API로 보내는 데이터: 해당 없음(로컬 시험만)
- 예상 임베딩·생성 호출량과 무료 한도 대비: 0 Neurons. 출력이 같으므로 병합 뒤 동기화도 재임베딩·색인 제외 변화 0
- 인덱스 버전 변경: 없음(`iv-4c0bc4fcc642` 유지). 보안 규칙 버전도 `sec-91a57f4542e8` 유지

## Ownership

| Area (paths) | Owner | Required review |
| --- | --- | --- |
| `redact.py`, `tests/unit/security/test_redact.py`, `TASK.md` | Byuntil | 사람 리뷰. PR 전 오케스트레이터 세션(구현 세션과 다른 세션)이 diff를 검토한다 |

## Existing user-owned changes

- 2026-10-28 `origin/main`(`580f83e`)에서 브랜치를 만들 때 `git status --short` 결과: 변경 없음

## Validation

```bash
python scripts/preflight.py
git diff --check
uv run ruff check .
uv run ruff format --check .
uv run qk-dev db up
QK_REQUIRE_LOCALDB=1 uv run pytest
node --test workers/relay/relay.test.ts
```

시험을 먼저 쓰고 지금 코드에서 실패하는 것을 확인한 뒤 고친다.

## Completion criteria

- `fffff:`·`f:f.`·`a.a.a.a:99999`·`::` 반복 10만 자 입력의 가림(TEXT·PATH·LINK)이 1초 안에 끝난다 — `pytest`
- 옛 `_mask_ipv6`(`origin/main`)와 무작위·적대적 입력(IPv4를 붙인 IPv6, 점·확장자 인접, `std::map` 꼴, 콜론만 있는 입력, 긴 16진 구간,
  IPv4·`host:port`·스킴과 섞인 입력)을 세 필드 종류에서 비교해 출력 차이가 0이다 — 비교 기록
- 기존 가림·보안 시험이 기대값 변경 없이 통과하고 `ADDRESS_POLICY_VERSION`이 `address-v6` 그대로다 — `pytest`, diff

## Decisions

- 2026-10-28 사용자 결정: #82는 Jira 없는 예외 작업이다.
- 2026-10-28 사실(시험 먼저): 새 성능 시험 21건 중 8건(`fffff:`·`f:f.`·`a.a.a.a:99999`·`::` × TEXT·PATH)이 수정 전 코드에서 실패했다.
  LINK와 `f:`·`ffff:`·`1:2:3:4:5:6:7:` 반복은 수정 전에도 1초 안이라 회귀 방지로 둔다. 수정 뒤 모두 통과.
- 2026-10-28 결정(구현): 글자로 먼저 거른 뒤 `ipaddress`를 부르는 방식 대신, IPv6 후보를 `ipaddress`가 받는 표기와 같은 RFC 3986 3.2.2 문법
  정규식(`IPV6`)으로 찾는다. 대안을 `::` 뒤 구간이 많은 것부터 두어 한 위치에서 처음 맞는 것이 가장 긴 유효 후보가 되게 했다. 정규식 검색이
  C 엔진 안에서 위치를 건너뛰므로 위치마다 Python 반복이 없다. `IP_MAX_LENGTH`와 `_is_ipv6`는 쓰지 않게 되어 지웠다(유효 IPv6는 45자를 넘지 않는다).
  `IPV6`는 `AddressPolicy.patterns`에 넣지 않았다(넣으면 출력이 같아도 보안 규칙 버전이 바뀐다). `SCHEME_CHARS`처럼 버전 재료 밖의 판정 상수다.
- 2026-10-28 사실(가장 긴 후보 시험): 경계 사례 10건(`1:2:3:4:5:6:7::9`, `::192.0.2.256`, `::ffff:192.0.2.01`, `std::map::f` 등)의 기대값은
  옛 코드 출력이다. 정규식 대안 순서를 뒤집으면 6건이 실패한다(돌연변이 확인).
- 2026-10-28 사실(측정, 로컬 1회, 10만 자 `safe_text`): 새 코드 TEXT·PATH·LINK 모두 0.03~0.09초. 옛 코드 TEXT는 `fffff:` 5.97초, `f:f.` 5.41초,
  `a.a.a.a:99999` 4.59초, `::` 2.86초, `:::` 2.87초, `f:f:f:f:f:f:f.` 6.76초, `f:f:f:f:f:f:1.2.3.` 6.60초, `1.2.3.4:` 4.74초.
- 2026-10-28 사실(옛·새 비교, 로컬): 정규식과 `ipaddress.IPv6Address`의 판정을 모든 문자열로 비교해 차이 0(알파벳 `0f:.1` 10자 이하,
  `0125:.` 9자 이하). `_mask_ipv6` 출력을 모든 문자열로 비교해 차이 0(`0f:.1` 9자 이하 2,441,405개, `a1:.g` 8자 이하 488,280개).
  이 저장소 추적 경로 873개의 PATH·TEXT 출력·판정 차이 0. 보안 규칙 버전은 `sec-91a57f4542e8` 그대로다.
  IPv4 꼬리 조합 7,516,890개(앞부분 10 × 옥텟 17⁴ × 뒷부분 9, 앞자리 0·256 이상 포함)의 `_mask_ipv6` 차이 0.
  무작위 합성 입력(16진·콜론·`::`·IPv4·IPv6·`std::map`·`host:port`·스킴·점·확장자·비ASCII 조각을 1~25개 이음) 시드 3개 × 30만 건에서
  `_mask_ipv6`·세 필드 종류 `safe_text`·`has_unsafe` 차이 모두 0(옛 코드가 IPv6를 가린 입력은 시드마다 약 25만 건).
  #79 검토 에이전트의 생성기(`fuzz.py`) 20만 건에서도 출력 차이 0, 예외 0, 두 번 가림 차이 0.
- 2026-10-28 오케스트레이터 diff 검토(구현 세션과 다른 세션, 구현은 고치지 않음): 승인 권고, blocker 없음.
  옛·새 비교를 따로 다시 했다. 구조화한 IPv6 무작위 30만 건과, 1~8구간 × `::` 위치 × IPv4 꼬리를 모두 조합한 654,444개(옛 코드가 가린 것 638,781)에서
  `_mask_ipv6`·세 필드 종류 `safe_text` 차이 0. 옛 모듈을 메모리에서만 바꿔 새 시험을 돌려 성능 시험 8건 실패를 확인했다.
  정규식 역추적을 노린 적대적 입력 18종 × 세 필드 종류에서 10만 자 최대 0.09초. 보안 규칙 버전 `sec-91a57f4542e8` 그대로.
  알아 둘 점: `IPV6`는 보안 규칙 버전 재료 밖이라, 뒤에 이 정규식을 고쳐 판정이 바뀌면 `ADDRESS_POLICY_VERSION`을 손으로 올려야 한다(옛 `ipaddress` 호출도 재료 밖이었다).
  판정이 Python `ipaddress`의 판별 동작이 아니라 정규식에 따르게 되어, Python 판이 바뀌어도 판정이 그대로다(지금 런타임 3.13.16에서 같음).
