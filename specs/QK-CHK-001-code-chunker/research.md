# Research: QK-CHK-001 코드 청커·코드 메타데이터

이 문서는 저장소 코드, QK-CHK-002·QK-STO-001·QK-SYN-001·QK-RET-001·QK-EMB-001 산출물, 아래 R-02의 로컬 실측으로 정했다.
실측은 모두 로컬에서 했다(외부 모델 호출 0건, 0 Neurons). 대상 저장소 사본 받기와 후보 라이브러리 임시 설치는 2026-10-26 사용자가 허용했다.
PyPI 휠 목록은 PyPI JSON API를 읽기 전용으로 조회해 확인했다(내려받기 없음).

## R-01 구문 해석: tree-sitter를 색인 전용 선택 의존성으로, Kotlin은 해석용 같은 길이 사본

- **Decision**:
  - 의존성: `tree-sitter==0.26.0`, `tree-sitter-java==0.23.5`, `tree-sitter-kotlin==1.1.0`을 색인 전용 선택 의존성(`[project.optional-dependencies] index`)과 `dev` 그룹에 고정해 더한다.
    QK-CHK-002의 `markdown-it-py`와 같은 자리다.
  - Kotlin 해석용 사본: 해석할 때만 `\bsuspend(?=\s*\{)`를 같은 길이의 `run    `으로 바꾼 사본을 해석기에 넘긴다. 바이트·줄 위치가 하나도 바뀌지 않으므로 노드 위치를 원문에 그대로 쓴다.
    청크 본문·시그니처·메타데이터는 원문에서 자른다. 이 바꿈 규칙은 코드 청킹 규칙 버전 재료다(R-08). 2026-10-26 사용자 결정("같은 길이 해석용 사본").
  - 지연 가져오기: `tree_sitter*`는 `chunking/code/parse.py`의 함수 안에서, `chunk_code`가 처음 해석할 때만 가져온다. `chunking.code`의 다른 모듈과 `chunking/__init__.py`·`service.py`는
    모듈 첫머리에서 `chunking.code`를 가져와도 되지만 `tree_sitter`를 가져오지 않는다. 그래서 해석기를 불러오다 실패해도 그 파일만 `PROCESSING_ERROR`이고 Markdown 동기화는 계속된다.
    꺼짐이면 해석기를 가져오지 않는다(R-15 경계 시험).
- **Rationale**:
  - Java: 백엔드는 Java 21(`build.gradle` toolchain)이다. tree-sitter-java 0.23.5로 1,128개 파일을 해석해 오류 파일 0개였다(R-02).
  - Kotlin: Android는 Kotlin 2.3.21이다. tree-sitter-kotlin 1.1.0만 쓰면 233개 중 11개가 오류였고, 11개가 모두 ViewModel이었다.
    가장 안쪽 오류 노드를 따라가 보니 원인은 문장 맨 앞의 `suspend { … }` 람다 식이었다. 문법이 이 `suspend`를 함수 수식어로 읽고, 오류가 클래스 전체로 번진다.
    바꾼 사본으로 해석하면 오류 11개 → 0개, 새로 깨진 파일 0개였다. ViewModel 14개가 모두 컴포넌트로 판정됐다(R-02).
  - 사본 규칙은 `suspend fun`, `suspend () -> T`, `_suspend` 같은 식별자를 바꾸지 않는다. 문자열·주석 안에서 바뀌어도 해석용 사본에만 생기므로 결과에 영향이 없다.
  - 휠(2026-10-26 PyPI 조회): 세 패키지 모두 linux x86_64(CI)와 aarch64(운영 OCI A1, `docs/ops/oci-production-store.md`)용 휠이 있고, Windows 휠도 있다.
    - tree-sitter 0.26.0: cp313 manylinux2014 x86_64·aarch64, win_amd64
    - tree-sitter-java 0.23.5, tree-sitter-kotlin 1.1.0: cp39-abi3 manylinux2014 x86_64·aarch64, win_amd64
    - 사용권은 셋 다 MIT다(tree-sitter는 분류자 `License :: OSI Approved :: MIT License`).
  - 실행 중에 내려받는 것이 없다. 질의응답 번들(Workers)에는 들어가지 않는다(`[project] dependencies = []`, spec Assumptions).
- **Alternatives considered**:
  - `tree-sitter-language-pack==1.22.1`: Kotlin 오류가 1개로 적었다. 하지만 PyPI 패키지와 별도로, 실행 중에 플랫폼별 해석기 묶음(네이티브 DLL)을 외부에서 내려받아
    `%LOCALAPPDATA%/tree-sitter-language-pack`에 둔다. 색인 실행 중의 네이티브 코드 내려받기는 재현성과 공급망 위험이 있어 고르지 않았다.
    측정 중 이 내려받기가 실제로 일어났다(`v1.22.1` 묶음 약 28 MB, 출처 URL과 해시는 기록하지 않았다. TASK.md).
  - 바꾸지 않고 대체 청킹(spec FR-019 그대로): ViewModel 11개의 심볼 경로와 컴포넌트 종류를 잃는다.
  - Kotlin용 구조 스캐너를 직접 구현: 의존성은 없지만 문자열 템플릿·원시 문자열·주석·제네릭을 다뤄야 해서 크기가 커지고 결함 위험이 크다.
  - `javalang` 같은 순수 Python Java 해석기: Java 21 문법(레코드, 패턴 매칭, 봉인 형식)을 다루지 못한다(측정하지 않음).
- **남는 위험**: 해석기 버전을 올리면 해석 결과가 바뀔 수 있다. 버전은 청킹 규칙 버전 재료라 바꾸면 인덱스 버전이 바뀐다. 다른 Kotlin 문법 결함이 새로 나오면
  그 파일은 spec FR-019대로 파일 전체 대체 청킹이 되고, 실행 요약의 "구문 해석 실패" 경고 수로 드러난다.

## R-02 대상 저장소 구조 측정

- **방법**: `specs/QK-CHK-001-code-chunker/measurement/measure_code.py`(스크립트 SHA-256 앞 12자리 `1cc6ad12e564`, 출력 `script_sha256_12`).
  원문·경로·심볼 이름을 출력하지 않는 집계 스크립트다. spec FR-010·013·014·020·021을 거칠게 흉내 내고, 상한 초과 나누기와 맥락 줄 생략은 하지 않는다. 실행 명령은 그 파일 머리말에 있다.
- **측정 조건**(2026-10-26):
  - 백엔드: `dnd-side-project/dnd-15th-2-backend` 커밋 `6aeccd039b825dcd7a2b6c046a34ef72089a1f78`(그날 `main` 머리, QK-CHK-002 R-02와 같은 커밋)
  - Android: `dnd-side-project/dnd-15th-2-android` 커밋 `0314755ed916c021448c80394f05412d1d454ebb`(그날 `main` 머리)
  - 해석기: R-01 버전과 해석용 사본 규칙
  - 실제 토큰: `tokenizers` 0.23.3 + `BAAI/bge-m3` 토크나이저. 리비전 `5617a9f61b028005a4858fdac845db406aefb181`이고 QK-CHK-002 R-03과 같은 파일(`tokenizer.json` SHA-256 `21106b6d…`)이다.
  - 예상 토큰: UTF-8 바이트 ÷ 3.5. 예상 Neurons: 임베딩 입력 바이트 ÷ 1.4 × 1,075/백만(QK-EMB-001 보정 계수)
  - 규칙: R-04의 채택 규칙 세 가지(spec 개정판)를 적용했다.

| 항목 | 백엔드 | Android |
| --- | --- | --- |
| 대상 파일(본문 / 테스트) | Java 777 / 351 | Kotlin 227 / 6 (본문에 `build-logic/` 11개 포함) |
| 원문 바이트(본문 / 테스트) | 1,880,241 / 3,313,745 | 432,610 / 3,010 |
| 기본 제외 규칙에 걸린 파일 | 0 | 0 |
| 비밀값 규칙에 걸린 파일 | 테스트 9(`assigned-secret`), 본문 0 | 0 |
| 해석 오류 파일 | 0 | 0 (해석용 사본이 바꾼 파일 11) |
| 청크 수(본문 + 테스트) | 10,800 | 1,021 |
| 청크 종류 | 메서드 7,178, 형식 머리(첫 필드 묶음과 합친 것 포함) 1,399, 파일 머리 1,119, 요약 1,040, 필드 묶음 61, 초기화 3 | 형식 머리 262, 파일 머리 233, 메서드 225, 최상위 함수 114, 요약 73, 파일 요약 70, 최상위 프로퍼티 38, 초기화 5, 필드 묶음 1 |
| 임베딩 입력 예상 토큰 p50 / p90 / p99 / 최대 | 170 / 436 / 966 / 3,090 | 98 / 347 / 1,239 / 5,241 |
| 상한 후보를 넘는 청크(나누기 전) 1,200 / 1,500 / 2,000 | 47 / 12 / 5 | 12 / 10 / 4 |
| 헤더를 붙여 상한 1,200을 넘는 한 줄이 있는 파일 | 0 | 0 |
| 실제 토큰 ÷ 예상 토큰 p50 / p99 / 최대 / 전체 | 1.189 / 1.449 / 1.650 / 1.178 | 1.128 / 1.406 / 1.683 / 1.025 |
| 헤더 + 맥락 줄 바이트 ÷ 원문 바이트 | 0.45 | 0.36 |
| 예상 Neurons 본문 / 테스트 | 2,476 / 4,024 | 482 / 5 |
| Android 컴포넌트 | 0 | ViewModel 14, Composable 78, Activity 1, Application 1 |
| Android import 없이 컴포넌트 이름 상위 클래스를 쓰는 형식 | 0 | 0 |
| 테스트 메서드 / `@DisplayName` 붙은 것 | 2,082 / 2,082 | 6 / 0 |
| 같은 형식 안 같은 이름 멤버 묶음(오버로드 후보) | 435 | 0 |

- **해석**:
  - 본문 코드만 첫 활성화하면 보정 계수로 약 2,960 Neurons다. 백엔드 2,476에 Android 본문 482를 더한 값이고, Android `build-logic/`은 포함 패턴 밖이라 실제는 조금 작다.
    토크나이저 토큰 수로 잡으면 약 1,360이다. 예산 판정은 보정 계수를 쓰므로(QK-EMB-001) 보수 값 약 3,000으로 계획한다. 하루 색인 예산 5,000 안이다.
  - 테스트까지 넣으면 약 7,000으로 예산을 넘는다. 그래서 첫 활성화는 본문만 권고한다(2026-10-26 사용자 결정, R-13).
  - 상한 1,500을 넘는 청크는 22개(0.2%)로 나누기가 드물다.
  - 줄 길이 초과 실패는 0건으로 예상한다.
  - 오버로드는 흔하므로(435묶음) 심볼 이름에 매개변수 형식을 넣는 spec FR-020이 필요하다.
  - Composable은 어노테이션 86개 가운데 78개가 함수 선언에 붙었다. 나머지는 람다·형식 인자 위치로 보인다 `(추론)`.
  - 측정 스크립트는 R-05의 합치기 크기 규칙(머리 줄 포함, 머리만으로 목표 이상이면 합치지 않음)을 따르고, 형식 머리와 합친 청크에도 바깥 맥락 줄만 붙인다(spec FR-021).
    스크립트 해시는 줄 바꿈을 LF로 바꾼 뒤 계산해 체크아웃 환경과 관계없이 같다. 요약 본문 바이트는 청크 본문 바이트에 들어가므로 원문 바이트보다 크다.

## R-03 코드용 상한 1,500·목표 512 (예상 토큰)

- **Decision**: 코드 청킹 설정의 상한 `limit_tokens = 1500`, 목표 `target_tokens = 512`.
  - 설정 검사: 켜짐일 때 `qk-index check` 교차 검사(`config/check.py`, `_generation_check`와 같은 자리)에서 Context 예산과 비교한다.
    `QK_RETRIEVAL_CONTEXT_BUDGET`은 색인·질의 양쪽 진입점 설정이라 색인 쪽에서도 읽을 수 있다(`config/registry.py:181-188`).
  - 비교식: Context는 본문만 `RetrievalSettings.bytes_per_token`으로 센다(`retrieval/pack.py:52`). 그래서 `limit_tokens × 모델 bytes_per_token_estimate ÷ RetrievalSettings.bytes_per_token ≤ context_budget`이다.
    지금은 둘 다 3.5라서 `1,500 ≤ 2,000`이다.
  - 한계: Workers 쪽 설정 값이 색인 쪽과 같은지는 이 검사가 보장하지 않는다.
- **Rationale**:
  - 실제 ÷ 예상 토큰 최댓값이 1.683이다(R-02). 그래서 상한 1,500인 청크의 실제 토큰은 약 2,525 이하로, bge-m3 한도 8,192에 여유가 크다.
  - QK-CHK-002 `ChunkingSettings`와 같은 안전 검사(1,500 × 3.5 ÷ 1.2 = 4,375 ≤ 8,192)도 통과한다.
  - Context에 상한 크기 청크 하나를 넣어도 500이 남아 다른 중심 청크나 이웃이 들어갈 수 있다. 상한을 2,000으로 두면 첫 중심 청크일 때만 들어간다(spec FR-016).
  - 목표 512는 QK-CHK-002와 같다. 코드에서 목표는 필드 묶음, 형식 머리 합치기, 대체 청크, 상한 초과 나누기에만 쓰인다.
- **Alternatives considered**: 상한 2,000은 나뉘는 청크가 9개로 줄지만 Context에 들어가기 어렵다. 1,200은 나뉘는 청크가 59개로 늘어 시그니처 반복 비용이 커진다.

## R-04 작은 청크 규칙: 세 가지 채택

- **Decision**: 2026-10-26 사용자 결정으로 다음 세 규칙을 spec에 반영했다. 메서드끼리는 합치지 않는 국소성(spec SC-003)은 모두 지킨다.
  - (1) 패키지 경로가 원본 위치의 경로 구성 요소에 있으면 검색 헤더에서 패키지를 뺀다(spec FR-021).
  - (2) 형식 선언 머리 바로 뒤가 필드·프로퍼티 선언이면 머리와 첫 필드 묶음을 한 원문 청크로 합친다(spec FR-010).
  - (3) 본문 있는 멤버가 없는 형식과 Kotlin 파일은 요약을 만들지 않는다(spec FR-013·014). 본문 있는 멤버에는 중첩 형식 선언을 넣는다(plan 검토 M1 반영, 2026-10-26 사용자 결정).
- **측정**: R-02 조건, 두 저장소 합계, 테스트 포함. 네 줄 모두 같은 스크립트(`1cc6ad12e564`)로 쟀다.

| 규칙 | 해석용 사본 | 청크 수 | 본문 32토큰 미만 청크 | 헤더 바이트 | 예상 Neurons(본문 코드) |
| --- | --- | --- | --- | --- | --- |
| spec 승인판 | 끔(`--no-parse-copy`) | 12,947 | 2,865 | 2,086,746 | 3,387 |
| spec 승인판 | 켬 | 13,061 | 2,900 | 2,110,876 | 3,427 |
| (1)만 | 켬 | 13,061 | 2,900 | 1,746,659 | 3,247 |
| (1)+(2)+(3) | 켬 | 11,821 | 1,997 | 1,584,267 | 2,958 |

- **Rationale**: 헤더·맥락 줄 비용과 한두 줄짜리 형식 머리·DTO 요약이 비용과 청크 수를 키웠다. 승인판(사본 켬) 대비 효과는 다음과 같다.
  - 본문 코드 비용: 약 13.7% 줄었다.
  - 청크 수: 약 9.5% 줄었다.
  - 작은 청크: 약 31.1% 줄었다.
- **Alternatives considered**: 접근자(게터·세터) 같은 작은 메서드를 합치기. 메서드 국소성이 깨지고(SC-003) 메서드 단위 출처가 흐려져 하지 않았다. 작은 메서드 1,065개는 남는다.

## R-05 청크 단위와 해석기 노드 대응

- **Decision**: spec FR-010의 단위를 해석기 노드로 다음처럼 정한다.

| spec 단위 | Java 노드 | Kotlin 노드 |
| --- | --- | --- |
| 형식 선언 | `class_declaration`, `interface_declaration`, `enum_declaration`, `record_declaration`, `annotation_type_declaration` | `class_declaration`(interface·enum class 포함), `object_declaration`, `companion_object` |
| 형식 본문 | `class_body`, `interface_body`, `enum_body`(+`enum_body_declarations`), `annotation_type_body` | `class_body`, `enum_class_body` |
| 메서드·생성자 | `method_declaration`, `constructor_declaration`, `compact_constructor_declaration`, `annotation_type_element_declaration` | `function_declaration`, `secondary_constructor` |
| 초기화 블록 | `static_initializer`, `block` | `anonymous_initializer` |
| 필드·프로퍼티 | `field_declaration`, `constant_declaration` | `property_declaration` |
| 머리 항목 | `enum_constant` | `enum_entry` |
| 주석 | `line_comment`, `block_comment` | `line_comment`, `block_comment` |

- **주석·닫는 줄**: 멤버 앞에 붙어 이어지는 주석 노드는 그 멤버 청크에 들어간다. 멤버에 붙지 않은 주석과 형식 닫는 줄은 앞 청크에 붙는다.
  멤버에 붙지 않은 주석은 멤버가 끝난 뒤 다음 멤버 전에 빈 줄로 떨어진 주석 묶음이다. 공백 아닌 줄을 한 번씩만 덮는지는 단위 시험이 줄 셈으로 확인한다(spec SC-002).
- **표에 없는 노드**: 해석기가 노드를 주지만 위 표에 없는 노드(예: 형식 본문 안의 세미콜론, Kotlin `getter`)는 앞 청크에 붙는다.
- **해석 오류**: `has_error`가 하나라도 있으면 파일 전체를 대체 청킹한다(spec FR-019).
- **시그니처 끝 줄**: 본문 노드(`block`, `constructor_body`, `function_body`, 형식 본문)가 시작하는 줄이다. 본문 노드가 없으면 선언 끝 줄이다(spec FR-013).
- **필드 묶음**: 원문 순서로 쌓고, 다음 필드를 더하면 목표 크기를 넘을 때 끊는다(탐욕).
- **형식 머리와 합치기**(spec FR-010): 첫 묶음 크기 계산에는 형식 머리 줄도 넣는다. 형식 머리만으로 목표 크기 이상이면 합치지 않고 필드는 따로 묶는다.
- **상한 초과 나누기**(spec FR-017): 멤버 본문 노드(`block`·`function_body`)의 바로 아래 자식 문장 노드가 끝나는 줄을 나누는 후보로 삼는다. 목표 크기 근처에서 마지막 후보를 고르고,
  후보가 없으면 아무 줄 경계를 고른다. 형식 머리·파일 머리·필드 묶음은 줄 경계에서 나눈다.
- **대체 청킹**(spec FR-019): 빈 줄로 나뉜 블록을 원문 순서로 쌓아 목표 크기에서 끊는다(탐욕). 상한을 넘는 블록은 줄 경계에서 나눈다.

## R-06 심볼 이름·시그니처·메타데이터 추출

- **Decision**:
  - 이름: Java는 `identifier`이고 Kotlin은 `identifier`·`type_identifier`·`simple_identifier`다. `companion_object`는 이름이 없으면 `Companion`이다.
  - 매개변수 형식 목록(spec FR-020):
    - Java: `formal_parameter`·`spread_parameter`의 형식 노드다.
    - Kotlin: `parameter`의 형식 노드 전체다. `user_type`·`nullable_type`·`function_type`·`parenthesized_type`을 포함한다.
    - 공통 처리: 형식 노드 원문에서 형식 어노테이션(`@Composable` 등)을 빼고 공백을 지운다. 수식어·이름·기본값은 빼고, 가변 인자는 `형식...`으로 쓴다.
  - Kotlin 확장 함수의 수신 형식: `function_declaration`의 이름 앞 형식 노드다.
  - 시그니처: 선언 시작부터 시그니처 끝(본문 여는 문자 앞)까지의 원문이다. 선언 어노테이션 노드는 빼고 공백 하나로 정리한다.
  - 어노테이션 이름: `modifiers` 아래 `annotation`·`marker_annotation`의 이름에서 패키지를 뺀 마지막 부분이다.
  - 형식 선언 종류: 노드 종류와 키워드(`interface`, `enum`, `record`, `object`)이고, 수식어는 `class_modifier`·Java 수식어 원문이다.
  - 상위 클래스(spec FR-024): Java `superclass`, Kotlin `delegation_specifier` 가운데 `constructor_invocation`을 가진 것이다.
- **Rationale**: 모두 노드 원문에서 결정적으로 나온다. 이름 해석(같은 이름 형식의 패키지 찾기)은 하지 않는다(spec FR-003).
  Compose 함수는 `() -> Unit` 같은 함수 형식 매개변수가 많아서(Composable 78개), 형식 노드 전체를 써야 오버로드 구분(spec SC-006)이 지켜진다(plan 검토 M8).

## R-07 검색 헤더·맥락 줄·임베딩 입력 텍스트 형식

- **Decision**: 코드 청크의 텍스트를 다음처럼 만든다.

```text
검색 헤더:   <위치> <언어>[ <패키지>]\n<심볼 경로를 " > "로 이음> [<청크 종류>][ <표시 이름>]\n
맥락 줄:     바깥 형식부터 각 형식의 선언 어노테이션 줄 + 선언 줄(spec FR-021)
임베딩 입력: 검색 헤더 + 맥락 줄 + "\n" + (반복 줄 + "\n") + 청크 본문
키워드 검색 텍스트: 기준선이면 검색 헤더 + 맥락 줄 + 청크 본문. 식별자 분해면 그 뒤에 QK-RET-001 분해 낱말 줄
```

  - `<패키지>`는 R-04 (1)에 따라 뺀다. 판정 조건은 `"/" + 패키지 경로 + "/"`가 `"/" + 위치` 안에 있는 것이다. 경로 구성 요소 경계로 비교하므로 `a/b`가 `x/a/bc/`에 맞지 않는다.
  - 표시 이름은 테스트 메서드일 때만 붙는다.
  - 형식 선언 머리 청크(첫 필드 묶음과 합친 것 포함)와 그 형식의 요약 청크에는 바깥 형식의 맥락 줄만 붙는다.
- **상한 초과**: 크기가 상한을 넘으면 맥락 줄을 바깥 형식부터 형식 단위로 빼고 그 청크에 "맥락 줄 생략" 경고를 붙인다(spec FR-018). 다 빼도 넘으면 기존 실패 유형을 쓴다.
- **Rationale**: QK-CHK-002 R-09의 "헤더는 본문 밖, 임베딩 입력·키워드 텍스트 앞" 원칙과 같다. 키워드 규칙 함수는 그대로 쓰고 입력만 넘긴다(spec FR-022).
- **보충**(tasks 검토 M3, 2026-10-26 사용자 결정): 정확한 문자열은 기존 `search_text`·`embedding_text`를 그대로 다시 쓰는 contracts/chunker.md 8절 형식이다. 청크 종류는 `CodeChunkKind` 값(예: `METHOD`)으로 쓴다.

## R-08 코드 청킹 규칙 버전 `chk-code-<12자리 해시>`

- **Decision**: QK-CHK-002 R-07과 같은 방식이다. 재료는 정렬한 JSON의 SHA-256 앞 12자리다. 재료 항목은 다음과 같다.
  - 판수: 규칙 판수, 헤더 형식 판수, 키워드 검색 텍스트 형식 판수, 임베딩 입력 형식 판수
  - 설정: 상한, 목표, 모델, 최악 바이트/토큰
  - 해석기: 이름·버전 셋. 버전은 `chunking/code/version.py`의 고정 상수(`tree-sitter 0.26.0`, `tree-sitter-java 0.23.5`, `tree-sitter-kotlin 1.1.0`)다.
    Markdown처럼 모듈을 가져와 `__version__`을 읽지 않는다(`chunking/blocks.py:5-8`). 그래서 버전 계산(`version_for`, `current_spec`, 설정 검사)이 네이티브 라이브러리를 불러오지 않는다.
    단위 시험이 상수와 `importlib.metadata.version()`(네이티브를 불러오지 않는다)이 같은지 확인한다(plan 재검토 N1)
  - Kotlin 해석용 사본 규칙 식별자(`suspend-lambda-v1`)
  - 판수: 맥락 줄 생략 규칙 판수, 대체 청킹 전환 규칙 판수, 요약 생략 규칙 판수
  - 목록: Android 기본 형식 목록(`ANDROID_BASES`), 컴포넌트 이름 규칙(`COMPONENT_SUFFIXES`, tasks 검토 M5 보충), 테스트 소스 세트 목록, 테스트 어노테이션 목록
  - 키워드 규칙

  키워드 규칙은 코드 버전에 처음부터 들어간다. 기준선만 재료에서 빼는 예외(QK-RET-001 R-04)는 Markdown 버전의 기존 값을 지키려던 것이라 새 버전에는 필요 없다.
  첫 값은 구현 때 계산하고 단위 시험에 고정한다.
- **Rationale**: spec FR-027의 재료 요건(구문 해석 실패 판정, 맥락 줄 생략 규칙, 해석기 버전)을 모두 담는다. 경고 판정만 바꾸는 일은 없다. 두 경고 모두 청크를 바꾸는 판정과 붙어 있기 때문이다.

## R-09 켜기 설정, 인덱스 버전 합치기, 켜짐 방지

- **Decision**:
  - 설정 자리(plan 검토 H1 반영): 코드 청킹 설정은 `ChunkingSettings` 밖의 별도 타입 `CodeChunkingSettings`로 둔다. `ChunkingSettings`의 필드와 `asdict` 결과는 바뀌지 않는다.
    그래서 `devtools/measure.py:134`의 출력과 `tests/unit/devtools/test_measure.py:252-257` 고정값이 그대로다. 2026-10-26 사용자 결정("설정을 밖에 둠").
  - 넘기는 길:
    - `chunk_screened(passed, settings, *, code=None)`가 키워드 전용 인자를 하나 받는다. 기존 위치 인자 호출은 그대로다.
    - `SyncDependencies`에는 끝에 기본값 `None`인 `code_chunking` 필드를 더한다(`sync/run.py:30-38`, 위치 인자 생성자 호환).
  - 버전 함수(위치 `chunking/version.py`. 메타데이터 스키마 버전 함수는 `sync/keys.py`):
    - `index_chunking_version(settings, code)`: 꺼짐(`code is None`)이면 Markdown 버전 그대로, 켜짐이면 `"<chk-md-…>+<chk-code-…>"`
    - `metadata_schema_version(code)`: 꺼짐 `meta-v1`, 켜짐 `meta-v2`(R-11)
  - `sync/run.py:current_spec`: 두 값을 `index_version_id`에 넘기고, `IndexSpec(..., metadata_schema_version=metadata_schema_version(code))`도 채운다(plan 검토 M3).
    지금은 `IndexSpec.metadata_schema_version` 기본값 `meta-v1`(`ports/sync.py:27`)이 그대로 `qk.index_version`에 기록되기 때문이다(`adapters/postgres/sync_store.py:66-69`).
  - `indexer/sync_cli.py:current_index_version(chunking=None, code=None)`: 같은 계산을 한다.
  - 설정을 읽는 곳(plan 검토 L8):
    - 동기화 실행(`build_runtime`)과 `index status`·`index` 읽기 명령(`indexer/sync_cli.py:289, 300`)은 같은 함수 `code_chunking_from(settings)`로 `QK_CODE_CHUNKING`을 읽는다.
      그래서 켜짐이면 상태 보고도 켜짐 버전을 쓴다.
    - 평가용 색인 준비(`devtools/eval_index.py:163-175`)는 이번에 바꾸지 않는다. 늘 꺼짐이다. `build_runtime(..., code=…)`은 `code` 인자를 따로 받는다.
      `chunking`을 명시해 넘기면(평가 준비가 그렇다) `code`를 넘기지 않는 한 꺼짐이다. `chunking`이 없을 때만 `code_chunking_from(settings)`을 읽는다(plan 재검토 N3).
      코드 청크 평가는 QK-STO-002·QK-EVL-001에서 정한다.
  - 꺼짐 결과: Markdown `chunking_version(settings)`의 재료는 명시한 항목만 쓰므로(`chunking/version.py:16-34`) `chk-md-20d966f730bb`가 그대로다. 인덱스 버전도 `iv-4c0bc4fcc642` 그대로다(spec SC-011).
  - 환경값: `QK_CODE_CHUNKING`(`off` 기본, `on`) 하나를 `config/registry.py`에 더한다. 상한·목표는 코드 상수다(Markdown과 같다).
  - 켜짐 방지(plan 검토 M2, 2026-10-26 사용자 결정 "미리 두고 검사로 막기", spec FR-030):
    - `qk-index check`는 켜짐이고 계산한 인덱스 버전이 `INDEX_KEYWORD_RULES`(`domain/keyword_rules.py:17-22`)에 없으면 `CODE_INDEX_VERSION_UNREGISTERED` 오류를 낸다.
      `config/check.py`는 질의 경로도 가져오므로(`query/worker.py:14`, `query/server.py:12`, `query/app.py:7`), 이 검사는 `_generation_check`(`config/check.py:99-101`)처럼
      함수 안에서 `chunking.version`·`sync.keys`를 가져오고, INDEX 진입점에서 `QK_CODE_CHUNKING=on`일 때만 계산한다. 그래서 질의 경로에 `markdown_it`·`chunking`이 들어가지 않는다(plan 재검토 N2).
    - `qk-index run`은 같은 조건이면 원본 호출 전에 멈춘다(설정 검사가 run 앞에서 도는 기존 순서).
    - 대응표에 새 인덱스 버전을 더하는 일은 켜는 변경(QK-STO-002 뒤)에서만 한다.
- **Rationale**:
  - 켜짐이 아닌 한 인덱스 버전 재료·대응표·고정값 시험·측정 출력이 한 글자도 바뀌지 않는다.
  - 환경값만 실수로 바꿔도 동기화가 인덱스 버전 불일치(`sync/run.py:86-87`)로 모든 자료원을 보류하지 않고, 설정 검사에서 먼저 멈춘다.
  - 합친 문자열을 담을 열은 모두 길이 제약 없는 `text`다. `qk.index_version.chunking_version`은 `0001_initial_schema.sql:13`, `qk.sync_run.chunking_version`은 `0004_sync.sql:35`다.
    그래서 마이그레이션이 필요 없다.
- **Alternatives considered**:
  - `ChunkingSettings.code` 필드: 측정 출력 고정값 시험이 깨진다(H1).
  - 켜짐 재료를 켜는 변경으로 미루기: 켜는 변경이 커지고 켜짐 경로가 그때까지 시험되지 않는다.
  - 두 버전을 해시 하나로 합치기: 어느 쪽이 바뀌었는지 기록에서 바로 읽을 수 없다.

## R-10 문서별 변경 판정과 실행 기록

- **Decision**:
  - 문서별 판정: `sync/plan.py:87`의 `change_reason` 호출에 넘기는 청킹 버전을 `version_for(content, settings, code)`로 바꾼다. 이 함수는 코드 청킹 대상(FR-001)이면 코드 버전, 아니면 Markdown 버전을 준다.
    문서별 저장값 `processed_chunking_version`에는 그 문서를 맡은 청커의 버전이 들어간다(지금도 `chunked.chunking_version`, `sync/execute.py:159`).
  - 실행 기록(plan 검토 M4): 실행 기록 요약은 `sync/plan.py:216`이 `ChunkingSummary.from_results(chunk_results)`로 다시 계산한다.
    - `from_results(results, *, chunking_version=None, code_chunking_version=None)`에 키워드 인자 둘을 더한다.
    - 넘기면 `chunking_version`에 그 값(인덱스 버전용 청킹 문자열)이 쓰인다. 넘기지 않으면 지금처럼 첫 결과의 값이 쓰이고, 결과가 없으면 `""`다.
    - `sync/plan.py:216`과 `chunk_screened`가 두 값을 넘긴다. 그래서 첫 문서가 코드든 Markdown이든 같은 값이 남는다.
    - 결과가 하나 이상일 때만 넘긴다. 처리할 문서가 없는 계획의 요약은 지금처럼 `""`이고, 꺼짐이면 결과가 있을 때도 첫 결과의 값(Markdown 버전)과 같다. 그래서 꺼짐 요약 값이 지금과 같다(plan 재검토 N8).
  - 요약 필드: `ChunkingSummary`에 `code_chunking_version: str | None = None`과 코드 요약 항목(spec FR-031)을 기본값과 함께 더한다.
    실행 기록 JSON(`sync/report.py:summary_values`)에는 새 키가 빈 값으로 나온다. 기존 시험은 키 일부만 확인한다(`tests/unit/indexer/test_run_cli.py:153-166`, `tests/unit/sync/test_run_record.py:21`).
- **Rationale**: 지금 코드는 결과 첫 항목의 버전을 요약에 쓰고(`domain/chunking.py:117`) 모든 문서를 Markdown 버전과 비교한다. 이대로 켜면 코드 문서가 매번 다시 처리된다(spec FR-029).
  꺼짐이면 코드 자료는 "대상 아님"이라 저장되지 않으므로 기존 동작이 그대로다. 그 밖에 단일 버전과 비교하는 활성화·SQL 경로는 없다(plan 검토에서 grep으로 확인).

## R-11 코드 메타데이터 저장: 위치 값(`locator`)의 `code` 키

- **Decision**: 코드 청크의 `locator`는 `{"path": …, "lines": [시작, 끝], "code": {…}}`다. `code` 안의 키는 다음과 같다.
  - `language`, `package`, `symbol`, `signature`
  - `chunk_kind`, `type_kind`, `type_modifiers`, `annotations`
  - `test_code`, `test_method`, `display_name`, `component`
  - `summary`: 요약 청크 표시

  나머지 규칙은 다음과 같다.
  - 값은 JSON으로 저장되는 평범한 dict·list·str·bool이다(`adapters/postgres/store.py:394`의 `json.dumps(dict(locator))`).
  - 심볼 경로는 `heading_path`에 둔다(spec FR-020). Markdown 청크의 `locator`는 바뀌지 않는다.
  - 새 키 집합 도입은 메타데이터 스키마 변경으로 보고, 켜짐일 때 `meta-v2`로 올린다(spec FR-026, 2026-10-26 사용자 결정 N3).
- **Rationale**:
  - `locator`는 비어 있지 않은 JSON 객체이기만 하면 된다(`0001_initial_schema.sql:55`, `domain/store.py:144`).
  - 검색(`0002_search_functions.sql:22`), 문맥(`0005_retrieval.sql:68-71`), 추적(`adapters/postgres/store.py:341-363`) 결과의 `Provenance.locator`로 그대로 돌아온다.
    `path`·`lines` 키나 크기를 전제하는 SQL은 없다. 그래서 저장 스키마 마이그레이션 없이 spec FR-026을 지킨다.
  - 켜는 변경에 넣을 마이그레이션도 없다. 그 변경은 `QK_CODE_CHUNKING=on`, 대응표 추가, 고정값 시험 갱신만이다.
- **Alternatives considered**: 새 열(`code_meta jsonb`). 마이그레이션이 생기고 검색 SQL 반환 형식(`Provenance`)도 바꿔야 한다. 필터에 쓸 때(QK-TRK-001) 다시 정한다.
- **남는 위험**: 시그니처·심볼 이름이 `locator`에 들어가므로 `locator`를 그대로 로그에 쓰면 spec FR-007을 어긴다. 지금 코드에서 `locator`가 쓰이는 곳은 다음과 같다.
  - 검색 결과 Context로 넘어간다(`retrieval/pack.py:101`).
  - 생성 렌더링은 `path`만 읽는다(`generation/render.py:60`).
  - 검색 CLI는 `locator`를 출력하지 않고 `heading_path`만 출력한다(`indexer/search_cli.py:124-137`).

  청킹 요약·실행 기록·로그에 `locator`나 시그니처가 나오지 않는지 표지 문자열 시험으로 확인한다(quickstart 1절, spec SC-009).

## R-12 청커 나눠 주기와 결과 타입

- **Decision**:
  - 나눠 주기: `chunk_screened`는 Markdown이면 `chunk_markdown`(그대로), 코드 청킹 대상이면 새 `chunk_code`, 나머지는 기존 `NOT_MARKDOWN` 결과를 낸다.
    결과 값 이름 `NOT_MARKDOWN`은 바꾸지 않는다. 동기화(`sync/plan.py:104-111`)와 기록이 이 값을 쓰기 때문이고, 뜻은 spec의 "대상 아님"이다.
  - 경고: `StructureWarningKind`에 `PARSE_FALLBACK`(구문 해석 실패)과 `CONTEXT_OMITTED`(맥락 줄 생략)를 더한다. 실패 유형은 기존 셋 그대로다.
  - 결과 항목: 기존 `ChunkDraft`(`ChunkInput` + 검색 헤더 + 임베딩 입력 + 예상 토큰)를 그대로 쓴다. 저장·임베딩 코드는 바뀌지 않는다.
- **Rationale**: 임베딩 직전 검사는 임베딩 서비스가 캐시에 없는 모든 입력의 `embedding_text`에 한다(`indexer/embedding.py:17-24`, `embedding/service.py:155-172`).
  그래서 요약 청크도 따로 연결하지 않아도 검사를 받는다(spec SC-009). 시험은 빈 캐시에서 돌린다(quickstart 1절).

## R-13 코드 자료원 두 개: 이름·패턴·결정 기록

- **Decision**: `config/sources.toml`에 비활성으로 등록한다(spec FR-032·033).

| 이름 | 저장소 | 포함(첫 활성화 권고: 본문만) | 제외 |
| --- | --- | --- | --- |
| `dnd-backend-code` | `dnd-side-project/dnd-15th-2-backend` | `src/main/java/**/*.java` | 없음(기본 제외 규칙만) |
| `dnd-android-code` | `dnd-side-project/dnd-15th-2-android` | `app/src/main/**/*.kt`, `data/src/main/**/*.kt`, `domain/src/main/**/*.kt`, `presentation/src/main/**/*.kt` | 없음(`build-logic/`은 포함 패턴 밖) |

  - 범위 겹침 확인(spec US7-2): 두 단계로 확인한다.
    - 실측: 고정 커밋 트리를 `domain/scope.py:in_scope`로 두 패턴 집합에 맞춰 셌다. `dnd-backend-docs` 80개, `dnd-backend-code` 776개, 겹침 0개였다. Android 본문은 216개다.
    - 단위 시험: 같은 저장소 자료원 쌍의 포함 패턴 확장자 집합이 서로 겹치지 않는지 검사한다(문서 `.md` 대 코드 `.java`). 경로 목록을 고정값으로 저장하지 않아도 된다(plan 검토 L12).
  - 결정 기록: `docs/sdd/decisions/ADR-022-code-sources.md`. `ADR-021`은 진행 중인 `origin/chore/SCRUM-108-sync-failure-alert` 브랜치의 `ADR-021-sync-failure-alert.md`가 쓰고 있다.
    2026-10-26 사용자 결정으로 022를 쓰고, 병합 순서를 정할 때 번호를 다시 확인한다. 구현 단계에서 `templates/decision-record.md` 형식으로 쓴다. 담을 것은 다음과 같다.
    - spec FR-034 항목, 본문만 첫 활성화 권고(2026-10-26 사용자 결정), R-02 비용(보수 약 3,000 Neurons, 테스트 포함 약 7,000)
    - 선행 조건: spec FR-036의 자료원별 식별 명세(별도 세션 초안 QK-SYN-005), QK-STO-002
    - 한 번에 하나씩 켜기
    - 첫 수집량: 백엔드 본문 776개 파일을 분당 60요청(`domain/source_config.py:15-19` 기본값)으로 받으면 약 13분이고, 실행 상한 1,800초 안이다.
  - 테스트 소스 세트를 넣는 일은 첫 활성화 평가 뒤 별도 결정이다. 그때 백엔드 테스트 9개 파일의 `assigned-secret` 판정(R-02)을 사람이 확인한다.
- **Rationale**: 설정 검사는 비활성 자료원의 포함 패턴 확장자도 본다(`sources/scope_review.py:25-34`). `java`·`kt`는 허용 목록에 있고(`domain/redact.py:22`), 비활성이면 동기화 대상 선택에서 빠진다(`sync/identity.py:17`).

## R-14 성능 측정 조건 (spec SC-012)

- **Decision**: `measurement/measure_code.py --time-chunking`을 구현 단계에서 더한다. R-02의 고정 커밋 두 저장소 본문+테스트 1,361개 파일을 구현된 `chunk_code`로 3회 청킹하고 중앙값을 기록한다.
  두 저장소를 각각 돌려 합한다. 측정 장비는 개발자 PC(Windows 11, Python 3.13)다. 해석기 생성 시간은 포함하고, git에서 원문을 읽는 시간은 뺀다. 기준은 60초 이하다.
- **Rationale**: 해석만은 두 저장소 합쳐 약 1.0초였다(R-02 `parse_seconds` 0.91 + 0.12). 청크 조립을 더해도 60초에 여유가 크다 `(추론)`.

## R-15 모듈 경계

- **Decision**: 새 패키지 `src/qello_knowledge/chunking/code/`를 둔다(`__init__`, `parse`, `units`, `symbols`, `header`, `split`, `version`, `service`).
  - `tree_sitter*` 가져오기는 `chunking/code/parse.py` 함수 안(지연 가져오기, R-01)에만 둔다.
  - 도메인 타입은 `domain/chunking.py`에 더한다(표준 라이브러리만).
  - `tests/unit/test_boundaries.py`에 `tree_sitter` 금지 대상(질의 경로·도메인·`chunking/code/parse.py` 밖)을 더한다.
  - 시험(새 프로세스에서 한다):
    - 꺼짐으로 `chunk_screened`를 돌린 뒤 `sys.modules`에 `tree_sitter`가 없다.
    - 켜짐으로 `code_chunking_version`·`index_chunking_version`을 계산한 뒤에도 없다(N1).
    - `qello_knowledge.config.check`·`query.server`·`query.app`을 가져온 뒤 `qello_knowledge.chunking`·`markdown_it`이 없다(N2). `query.worker`는 Workers 전용 `js`를 가져와서
      로컬에서 가져올 수 없으므로 같은 가져오기 경로인 `config.check`로 확인한다. 지금 코드에서 이 조건은 성립한다(2026-10-26 확인).
- **Rationale**: QK-CHK-002 R-10과 같은 나눔이다. 해석기를 바꿀 때 고칠 곳이 하나다(C-06). 해석기 적재 실패가 Markdown 동기화로 번지지 않는다(plan 검토 M6).
