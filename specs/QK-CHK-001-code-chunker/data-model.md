# Data Model: QK-CHK-001 코드 청커·코드 메타데이터

새 타입은 `src/qello_knowledge/domain/chunking.py`에 더하는 불변 dataclass·StrEnum이다(표준 라이브러리만, research R-15). 기존 Markdown 타입의 필드와 값은 바꾸지 않는다.
저장 스키마, `ChunkInput`(QK-STO-001), SQL 함수는 바꾸지 않는다. 새 테이블·마이그레이션은 없다(research R-09·R-11).

## 입력

| 출처 | 쓰는 값 | 규칙 |
| --- | --- | --- |
| `ScreenedContent.content: SourceContent` | `body`, `content_format`, `location` | `content_format == CODE`, `location` 확장자가 `java`·`kt`, 코드 청킹 켜짐일 때만 코드 청킹(spec FR-001) |
| `ScreenedContent.item: SourceItem` | 결과에 그대로 붙인다 | 제목은 쓰지 않는다. 문서 제목은 파일 이름(spec FR-008) |

## ChunkingSettings

바꾸지 않는다. 필드와 `asdict` 결과가 그대로이므로 측정 출력(`devtools/measure.py:134`)과 그 고정값 시험이 그대로다(research R-09, plan 검토 H1).

## CodeChunkingSettings (새 타입, 켜짐일 때만 만든다)

코드 청킹 꺼짐은 이 값이 없는 상태(`None`)다. `chunk_screened(..., code=None)`, `SyncDependencies.code_chunking = None`으로 넘긴다(spec FR-030).

| 필드 | 타입 | 기본값 | 검증 |
| --- | --- | --- | --- |
| `model_version` | str | `@cf/baai/bge-m3` | `domain.embedding.MODELS`에 있어야 한다. `chunk_screened`가 바깥 `ChunkingSettings.model_version`과 같은지 확인하고, 다르면 `ValueError`다 |
| `target_tokens` | int | 512 (research R-03) | 1 이상, `limit_tokens` 이하 |
| `limit_tokens` | int | 1,500 (research R-03) | `__post_init__`에서 QK-CHK-002와 같은 안전 검사를 한다(`limit × bytes_per_token_estimate ÷ WORST_BYTES_PER_TOKEN ≤ max_input_tokens`). Context 예산 비교는 `qk-index check` 교차 검사(contracts/chunker.md 4절) |

키워드 규칙은 바깥 `ChunkingSettings.keyword_text_rule`을 함께 쓴다. Android 기본 형식, 테스트 소스 세트, 테스트 어노테이션 목록은 코드 상수다.
목록을 바꾸면 코드 청킹 규칙 버전이 바뀐다(research R-08, `COMPONENT_SUFFIXES` 포함). 상수는 `chunking/code/version.py`에 둔다(tasks T007).

| 상수 | 값 |
| --- | --- |
| `ANDROID_BASES` | `Activity`·`AppCompatActivity`·`ComponentActivity`·`FragmentActivity` → Activity, `Fragment`·`DialogFragment`·`BottomSheetDialogFragment` → Fragment, `ViewModel`·`AndroidViewModel` → ViewModel, `Service`, `BroadcastReceiver`, `ContentProvider`, `Application` |
| `COMPONENT_SUFFIXES` | Activity, Fragment, ViewModel, Service, BroadcastReceiver, ContentProvider, Application(이름 규칙, spec FR-024) |
| `TEST_SOURCE_SETS` | `src/test/`, `src/integrationTest/`, `src/androidTest/`, `src/testFixtures/`(경로 구성 요소, 어느 깊이든) |
| `TEST_ANNOTATIONS` | `Test`, `ParameterizedTest`, `RepeatedTest`, `TestFactory`, `TestTemplate` |
| `PARSER_VERSIONS` | `tree-sitter 0.26.0`, `tree-sitter-java 0.23.5`, `tree-sitter-kotlin 1.1.0` 고정 상수. 해석기를 가져오지 않고 버전 재료로 쓴다. 단위 시험이 `importlib.metadata.version()`과 비교한다(research R-08) |
| `KOTLIN_PARSE_COPY` | `\bsuspend(?=\s*\{)` → `run    `(같은 길이, 규칙 식별자 `suspend-lambda-v1`, research R-01) |
| 설정 오류 코드 | `CODE_LIMIT_OVER_CONTEXT_BUDGET`(research R-03), `CODE_INDEX_VERSION_UNREGISTERED`(research R-09) |

## 상태 값 (추가분)

| 타입 | 추가 값 | 뜻 |
| --- | --- | --- |
| `StructureWarningKind` | `PARSE_FALLBACK` | 구문 해석 실패로 파일 전체를 대체 청킹했다(spec FR-019). 줄 번호는 첫 오류 노드 줄 |
| `StructureWarningKind` | `CONTEXT_OMITTED` | 이 청크의 임베딩 입력에서 맥락 줄을 뺐다(spec FR-018). 줄 번호는 그 청크 시작 줄 |
| `CodeChunkKind` (새 StrEnum) | `FILE_HEAD`, `FILE_SUMMARY`, `TYPE_SUMMARY`, `TYPE_HEAD`, `METHOD`, `CONSTRUCTOR`, `TOP_FUNCTION`, `FIELDS`, `TOP_PROPERTIES`, `INITIALIZER`, `FALLBACK` | spec FR-023 청크 종류 11개. 첫 필드 묶음과 합친 형식 머리도 `TYPE_HEAD` |
| `AndroidComponent` (새 StrEnum) | `ACTIVITY`, `FRAGMENT`, `VIEW_MODEL`, `SERVICE`, `BROADCAST_RECEIVER`, `CONTENT_PROVIDER`, `APPLICATION`, `COMPOSABLE` | spec FR-024 |

`ChunkOutcomeKind`·`ChunkFailureKind`는 그대로다. 코드 청킹 대상이 아닌 자료는 `NOT_MARKDOWN`이다(research R-12).

## 코드 메타데이터 (위치 값 `locator["code"]`)

| 키 | 타입 | 값 |
| --- | --- | --- |
| `language` | str | `java` 또는 `kotlin` |
| `package` | str | 패키지 선언 값. 없으면 `""` |
| `symbol` | str | 심볼 이름(spec FR-020 표). 없으면 `""` |
| `signature` | str | spec FR-023. 없으면 `""` |
| `chunk_kind` | str | `CodeChunkKind` 값 |
| `type_kind` | str | 감싼 형식 선언 종류(`class`·`interface`·`enum`·`record`·`annotation`·`object`). 없으면 `""` |
| `type_modifiers` | list[str] | 원문 수식어(`data`, `sealed`, `abstract` 등), 원문 순서 |
| `annotations` | list[str] | 선언에 직접 붙은 어노테이션 단순 이름, 원문 순서 |
| `test_code` | bool | spec FR-025 |
| `test_method` | bool | spec FR-025 |
| `display_name` | str | 테스트 표시 이름. 없으면 `""` |
| `component` | str | `AndroidComponent` 값. 없으면 `""` |
| `summary` | bool | 요약 청크 표시(spec FR-013·014) |

- `locator`는 `{"path": <위치>, "lines": [시작, 끝], "code": {...}}`다. 요약 청크의 `lines`는 형식 선언(파일 요약은 파일) 전체 줄 범위다.
- `locator["code"]`는 JSON으로 저장되는 평범한 dict다(`adapters/postgres/store.py:394`). 따로 dataclass를 두지 않고, 만드는 함수가 위 키만 넣는다.
- 값은 `ChunkDraft.chunk`(이미 `repr=False`) 안에만 있어서 결과·요약의 `repr`에 나오지 않는다(spec FR-007).
- 심볼 경로는 `ChunkInput.heading_path`에 둔다(spec FR-020). 값은 모두 원문에서 결정적으로 나온다(research R-06).

## ChunkDraft·ChunkOutcome·ChunkedContent

기존 타입을 그대로 쓴다(research R-12).
- `ChunkDraft.chunk.search_text`는 키워드 검색 텍스트(research R-07)다.
- `ChunkDraft.search_header`는 검색 헤더, `ChunkDraft.embedding_text`는 헤더 + 맥락 줄 + 반복 줄 + 본문이다.
- `ChunkOutcome.chunking_version`은 코드 결과면 코드 청킹 규칙 버전이고, `split_blocks`는 상한 때문에 나뉜 원문 청크 수다.

불변식은 기존 그대로다. `CHUNKED`일 때만 `drafts`·`warnings`가 있다.

## ChunkingSummary (필드·인자 추가)

`from_results(results, *, chunking_version=None, code_chunking_version=None)`로 키워드 인자 둘을 더한다(research R-10).
넘기지 않으면 지금 계산(첫 결과의 값, 결과가 없으면 `""`) 그대로다. `chunk_screened`와 `sync/plan.py:216`은 결과가 하나 이상일 때만 두 값을 넘긴다.
그래서 꺼짐이면 요약 값이 지금과 같다(plan 재검토 N8).

| 필드 | 타입 | 규칙 |
| --- | --- | --- |
| `chunking_version` | str | 넘긴 경우 인덱스 버전용 청킹 문자열(research R-09). 꺼짐이면 지금과 같다 |
| `code_chunking_version` | str \| None (기본 `None`) | 켜짐일 때 코드 청킹 규칙 버전 |
| `by_code_kind` | Mapping[CodeChunkKind, int] (기본 빈 값) | 청크 종류별 수(spec FR-031) |
| `code_test_chunks` | int (기본 0) | `test_code`인 청크 수 |
| `code_components` | Mapping[AndroidComponent, int] (기본 빈 값) | 컴포넌트 종류별 형식 선언 수(Composable은 함수 수). 형식 머리 청크의 첫 조각에서만 형식 컴포넌트를, 메서드·최상위 함수 청크의 첫 조각에서만 Composable을 센다. 멤버 청크·요약·뒤 조각은 세지 않는다(tasks 검토 M4, 2026-10-26 사용자 결정) |

기존 필드의 계산은 그대로다. 코드 결과는 `by_outcome`·`chunk_count`·`by_failure`·`by_warning`·토큰 분포·`split_blocks`에 함께 들어간다.
꺼짐이면 추가 필드는 기본값이다. 실행 기록 JSON에는 새 키가 빈 값으로 나온다(research R-10).

## 버전 값

| 값 | 형식 | 재료·계산 |
| --- | --- | --- |
| Markdown 청킹 규칙 버전 | `chk-md-<12>` | 그대로(`chunking/version.py`) |
| 코드 청킹 규칙 버전 | `chk-code-<12>` | research R-08 |
| 인덱스 버전용 청킹 문자열 | 꺼짐 `chk-md-<12>`, 켜짐 `chk-md-<12>+chk-code-<12>` | `index_chunking_version(settings, code)`(research R-09) |
| 메타데이터 스키마 버전 | 꺼짐 `meta-v1`, 켜짐 `meta-v2` | `sync/keys.py:metadata_schema_version(code)`. `IndexSpec.metadata_schema_version`에도 같은 값을 넣는다(research R-09·R-11) |
| 인덱스 버전 | `iv-<12>` | `index_version_id(모델, 차원, 인덱스 버전용 청킹 문자열, 메타데이터 스키마 버전)`. 꺼짐이면 `iv-4c0bc4fcc642` |

## 자료원 설정 (config/sources.toml 추가분)

두 항목 모두 `enabled = false`, `kind = "github_repo_files"`, `auth = "GITHUB_API_TOKEN"`이다. 범위는 research R-13 표와 같다.
`[source.limits]`·`[source.retry]`는 적지 않아 `dnd-backend-docs`처럼 기본값을 쓴다(`domain/source_config.py:15-19`). 확인 기록(`config/source_reviews/`)은 만들지 않는다(spec FR-035).
