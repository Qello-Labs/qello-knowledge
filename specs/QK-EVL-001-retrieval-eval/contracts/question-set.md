# Contract: 질문 세트 파일

**Spec**: FR-001~FR-010 | **Research**: R-02, R-03

QK-STO-002(인덱스 버전 평가 게이트)와 QK-EVL-002(답변 평가)도 이 형식을 읽는다. 필드를 더하거나 뜻을 바꾸려면 이 문서를 고치고 형식 검증 시험을 같은 변경에서 고친다.

## 1. 파일과 위치

- 형식: TOML(UTF-8). 세트 하나에 파일 하나다.
- 위치: `eval/question_sets/<세트 ID>/v<버전>.toml`. 라벨 기준 설명은 `eval/question_sets/<세트 ID>/labeling.md`다.
- 파일 지문: 파일 바이트의 SHA-256(소문자 16진수 64자).
- 확정(`confirmed = true`)한 파일은 고치지 않는다. 질문·유형·근거 문서·핵심 사실을 바꾸려면 다음 버전 파일을 더하고 별도 커밋에 사유를 남긴다(AGENTS.md 3.4).

## 2. 머리 정보 `[set]`

| 필드 | 필수 | 형식 | 뜻 |
| --- | --- | --- | --- |
| `id` | 예 | `^[a-z0-9]+(-[a-z0-9]+)*$` | 세트 ID. 디렉터리 이름과 같다 |
| `version` | 예 | 정수 ≥ 1 | 파일 이름의 버전과 같다 |
| `created` | 예 | TOML 날짜 | 만든 날짜 |
| `confirmed` | 예 | 불리언 | 사람 확인으로 확정했는지 |
| `confirmed_on` | `confirmed = true`일 때 예 | TOML 날짜 | 확정 날짜. `false`면 두지 않는다 |
| `labeling` | 예 | 저장소 기준 경로 | 라벨 기준 설명 문서 |
| `origin` | 아니오 | 인라인 표 `{ id, version, document }` | 다른 세트에서 옮긴 경우 원본 세트 ID·버전·원본 문서 경로 |
| `shortfall` | 아니오 | 인라인 표 `{ <식별자 형태> = 정수 }` | 원본에 식별자가 5개보다 적은 형태와 실제 수(US2-3) |
| `[[set.sources]]` | 예(1개 이상) | `{ name, label_commit }` | 자료원 이름(`config/sources.toml`의 `name`)과 근거 문서를 고른 원본 리비전(40자 SHA) |

## 3. 질문 `[[question]]`

| 필드 | 필수 | 형식 | 뜻 |
| --- | --- | --- | --- |
| `id` | 예 | `^[A-Za-z0-9_-]{1,40}$`, 세트 안에서 유일 | 질문 ID |
| `text` | 예 | 문자열, 앞뒤 공백 뺀 길이 1~2,000자 | 질문 문장 |
| `type` | 예 | `code`·`doc`·`meeting`·`synthesis`·`no_answer` | 유형 |
| `label` | 예 | `done`·`pending` | 라벨 상태 |
| `evidence` | 예 | 인라인 표 배열 `{ source, location }` | 근거 문서 목록. `no_answer`면 빈 배열 |
| `facts` | 아니오 | 문자열 | 핵심 사실(QK-EVL-002용) |
| `origin` | 아니오 | `team`·`synthetic` | 질문 출처 |
| `query_form` | 식별자 세트에서 예 | `original`·`partial`·`sentence` | 질의 형태 |
| `identifier_form` | `query_form`이 `original`·`partial`이면 예 | `camel`·`pascal`·`acronym`·`digit`·`snake`·`kebab`·`url_path` | 식별자 형태. `sentence`면 두지 않는다 |
| `label_terms` | `query_form`이 있으면 예 | 문자열 배열(1개 이상) | 라벨 근거 낱말. `original`·`partial`은 식별자 원형 하나, `sentence`는 근거 문서를 고를 때 쓴 본문 낱말 |
| `original_number` | 아니오 | 문자열 | 옮겨 온 원본 번호 |

식별자 세트인지는 질문에 `query_form`이 있는지로 가린다. 한 세트 안에서 `query_form`이 있는 질문과 없는 질문을 섞지 않는다.

예(값은 설명용 가짜):

```toml
[set]
id = "example-identifiers"
version = 1
created = 2026-11-01
confirmed = false
labeling = "eval/question_sets/example-identifiers/labeling.md"
shortfall = { digit = 3 }

[[set.sources]]
name = "example-docs"
label_commit = "0000000000000000000000000000000000000001"

[[question]]
id = "camel-01-original"
text = "fooBarBaz"
type = "code"
label = "done"
origin = "synthetic"
query_form = "original"
identifier_form = "camel"
label_terms = ["fooBarBaz"]
evidence = [{ source = "example-docs", location = "docs/foo.md" }]
```

## 4. 검증 규칙

규칙 이름은 출력과 시험이 같이 쓴다. 검증은 모든 오류를 모은다. 출력에 `text`·`facts`·`label_terms` 값과 비밀값 규칙에 걸린 문자열을 넣지 않는다.

| 규칙 이름 | 거부하는 경우 |
| --- | --- |
| `toml_invalid` | TOML로 읽히지 않음(같은 키 두 번 포함) |
| `unknown_field` | 정해지지 않은 필드 |
| `required_missing` | 필수 필드 없음 |
| `bad_format` | 필드 형식이 표와 다름(ID·SHA·날짜·정수·배열) |
| `set_path_mismatch` | 파일 위치의 세트 ID·버전과 머리 정보가 다름 |
| `confirmed_date` | `confirmed`와 `confirmed_on`이 맞지 않음 |
| `source_duplicate` | 자료원 이름 중복 |
| `question_id_duplicate` | 질문 ID 중복 |
| `bad_enum` | 유형·라벨 상태·출처·질의 형태·식별자 형태가 정해진 값 밖(`unknown` 포함) |
| `text_empty` | 질문 문장이 비었음 |
| `text_too_long` | 질문 문장이 2,000자 초과(`RetrievalSettings.question_max_chars`) |
| `text_secret` | 질문 문장에 비밀값 규칙이 걸림(`domain/secret_rules.find_secrets`) |
| `evidence_unknown_source` | 근거 문서 자료원이 머리 정보 목록에 없음 |
| `evidence_bad_location` | 위치가 비었거나 `/`로 시작하거나 `://`·`\`·`..` 경로 조각을 담음 |
| `evidence_duplicate` | 한 질문 안에 같은 근거 문서가 두 번 |
| `evidence_required` | `label = done`이고 `type != no_answer`인데 근거 문서 0개 |
| `evidence_forbidden` | `type = no_answer`인데 근거 문서가 있음 |
| `form_mixed` | 한 세트 안에 `query_form` 있는 질문과 없는 질문이 섞임 |
| `form_fields` | `identifier_form`·`label_terms`가 질의 형태 규칙과 맞지 않음 |

## 5. 대상 지정 경고 (`--target`)

평가 대상을 함께 주면 질문마다 근거 문서를 그 대상의 문서 표(research R-04)에서 찾는다. 하나도 없으면 `evidence_unindexed`, 일부만 없으면 `evidence_partly_unindexed`를
질문 ID와 빠진 근거 위치로 경고한다. 경고는 통과·거부에 영향이 없다. 이 확인은 평가 대상 로컬 데이터베이스만 읽는다(FR-007).
