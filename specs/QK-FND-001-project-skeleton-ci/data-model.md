# Data Model: QK-FND-001

이 명세는 DB 스키마를 만들지 않는다(QK-STO-001 범위). 아래는 코드 안의 값 객체다.

## SettingSpec (설정 항목 정의)

| 필드 | 형식 | 규칙 |
| --- | --- | --- |
| `name` | str | 대문자·숫자·밑줄. 레지스트리 안에서 유일하다 |
| `description` | str | 비어 있지 않다. `.env.example`과 문서에 그대로 쓴다 |
| `entrypoints` | frozenset[`Entrypoint`] | `QUERY`, `INDEX` 중 하나 이상 |
| `required` | bool | 그 진입점에서 반드시 있어야 하는지 |
| `secret` | bool | 비밀 항목이면 `default`는 `None`이어야 한다(레지스트리 생성 시 검사) |
| `default` | str \| None | 비밀이 아닌 항목만 가질 수 있다 |
| `validator` | 이름이 붙은 형식 규칙 | 값을 받아 통과 여부만 돌려준다. 오류 문구에 값을 넣지 않는다 |

초기 레지스트리(`docs/sdd/research/tokens.md` 6절 이름을 그대로 쓴다):

| 이름 | 진입점 | 필수 | 비밀 | 형식 규칙 |
| --- | --- | --- | --- | --- |
| `DATABASE_URL` | 둘 다 | 예 | 예 | `postgres` 또는 `postgresql` 스킴의 URL |
| `GITHUB_API_TOKEN` | 색인 | 예 | 예 | `ghp_` 또는 `github_pat_`로 시작 |
| `CLOUDFLARE_API_TOKEN` | 색인 | 예 | 예 | 공백 없는 40자 이상 |
| `CLOUDFLARE_ACCOUNT_ID` | 색인 | 예 | 아니요 | 32자리 16진수 |
| `DISCORD_APPLICATION_ID` | 질의응답 | 예 | 아니요 | 숫자 17~20자리 |
| `DISCORD_PUBLIC_KEY` | 질의응답 | 예 | 아니요 | 64자리 16진수 |
| `DISCORD_BOT_TOKEN` | 질의응답 | 아니요 | 예 | 공백 없는 50자 이상 |
| `QK_LOG_LEVEL` | 둘 다 | 아니요 | 아니요 | `DEBUG`, `INFO`, `WARNING`, `ERROR` 중 하나. 기본 `INFO` |

- 질의응답 진입점은 Workers AI를 바인딩으로 쓰므로 Cloudflare 토큰을 받지 않는다(ADR-008, C-09).
- `DISCORD_BOT_TOKEN`은 HTTP 상호작용만 쓰면 필요 없어 선택 항목이다. 필요 여부는 QK-BOT-001에서 정한다.
- 항목의 실제 필요 여부와 형식은 후속 명세가 바꿀 수 있다. 바꿀 때는 레지스트리 한 곳만 고친다.

## SettingStatus

`OK`, `MISSING`(없음·빈 문자열·공백뿐), `INVALID`(형식 오류). 기본값을 쓴 경우는 `OK`다.

## CheckReport (설정 점검 결과)

| 필드 | 형식 | 규칙 |
| --- | --- | --- |
| `entrypoint` | `Entrypoint` | 점검한 진입점 |
| `items` | list[(name, `SettingStatus`)] | 그 진입점이 쓰는 항목만, 이름순 |
| `ok` | bool | 필수 항목이 모두 `OK`이고, 값이 있는 선택 항목도 `INVALID`가 아니다 |

값은 담지 않는다. 출력 형식은 [contracts/cli.md](contracts/cli.md)를 따른다.

## Settings (로딩 결과)

- 진입점별로 쓰는 항목만 담은 읽기 전용 매핑이다. 비밀 값은 `SecretValue`로 감싼다.
- `SecretValue`의 `str`·`repr`은 `"***"`이다. 실제 값은 `reveal()`로만 꺼내고, 어댑터 안에서만 부른다.
- 원천 우선순위: 실행 환경 변수 > `.env` > `default`.

## ResponseSample (응답 샘플)

`tests/fixtures/responses/<api>/<이름>.json`

| 필드 | 규칙 |
| --- | --- |
| `_meta.source_api` | 예: `github.rest.repos.get-content` |
| `_meta.saved_at` | `YYYY-MM-DD` |
| `_meta.redactions` | 지운 필드 목록. 토큰·계정 식별자는 저장 전에 지운다 |
| `body` | 저장한 응답 본문 |

## CI 검사 결과

GitHub Actions job 단위로 표시한다. job 이름이 검사 종류다(`test`, `lint`, `secrets`). 러너 장애나 시간 초과는 `failure`·`cancelled`로
남고 통과로 표시되지 않는다.
