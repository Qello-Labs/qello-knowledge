# Contract: 코드 청커 진입점과 버전

모듈: `qello_knowledge.chunking`(기존 공개 이름 유지)과 `qello_knowledge.chunking.code`.
- `tree_sitter*`는 `chunking/code/parse.py` 함수 안에서만, `chunk_code`가 처음 해석할 때 가져온다(지연 가져오기, research R-01·R-15).
- `qello_knowledge.chunking`은 첫머리에서 `chunking.code`를 가져와 `chunk_code`를 공개해도 된다. 그래도 `tree_sitter`는 불러오지 않는다.
- 버전 함수(1~3절)는 해석기를 불러오지 않는다. 해석기 버전은 고정 상수다(research R-08).
- 타입은 [data-model.md](../data-model.md)를 따른다. 외부 호출, 저장, 로그 출력이 없다(spec FR-004, FR-007).

## 1. code_chunking_version

```python
def code_chunking_version(code: CodeChunkingSettings, settings: ChunkingSettings) -> str
```

- 반환값은 `chk-code-` 뒤에 16진수 12자리를 붙인 값이다(research R-08). `settings`에서는 키워드 규칙만 읽는다.
- 재료 항목 하나라도 바뀌면 값이 바뀌고, 같은 설정이면 같은 값이다(spec FR-027, SC-010).

## 2. index_chunking_version, metadata_schema_version

```python
# chunking/version.py
def index_chunking_version(settings: ChunkingSettings, code: CodeChunkingSettings | None = None) -> str
# sync/keys.py
def metadata_schema_version(code: CodeChunkingSettings | None = None) -> str
```

- 꺼짐(`code is None`): `chunking_version(settings)`(지금 값)와 `"meta-v1"`을 돌려준다.
- 켜짐: `f"{chunking_version(settings)}+{code_chunking_version(code, settings)}"`와 `"meta-v2"`를 돌려준다(research R-09·R-11).
- `sync/run.py:current_spec(deps)`는 아래 값을 만든다(plan 검토 M3). `IndexSpec`의 다섯 필드가 모두 채워진다.

  ```python
  model = MODELS[s.model_version]  # ModelSpec
  IndexSpec(
      index_version_id(model.model_version, model.dimension, index_chunking_version(s, c), metadata_schema_version(c)),
      model.model_version,
      model.dimension,
      index_chunking_version(s, c),
      metadata_schema_version=metadata_schema_version(c),
  )
  ```
- `indexer/sync_cli.py:current_index_version(chunking=None, code=None)`도 같은 계산을 한다.
- 보장: 꺼짐이면 결과가 `iv-4c0bc4fcc642`·`meta-v1`이다(spec SC-011). 켜짐이면 Markdown·코드 버전 중 하나만 바꿔도 결과가 바뀐다.

## 3. version_for

```python
def version_for(content: SourceContent, settings: ChunkingSettings, code: CodeChunkingSettings | None = None) -> str
```

- 코드 청킹 대상(spec FR-001)이면 `code_chunking_version(code, settings)`를, 아니면 `chunking_version(settings)`를 돌려준다.
- `sync/plan.py`가 `change_reason`에 이 값을 넘긴다(research R-10). 꺼짐이면 모든 자료에 지금과 같은 값을 준다.

## 4. 설정과 설정 검사

- 환경값: `QK_CODE_CHUNKING`은 `off`(기본)와 `on` 두 값만 받는다. 다른 값은 설정 오류다(`config/registry.py`).
- 읽기 함수: `code_chunking_from(settings) -> CodeChunkingSettings | None` 하나로 읽는다.
  `index status` 같은 읽기 명령과 `current_index_version`을 부르는 곳이 이 함수를 쓴다(research R-09, plan 검토 L8).
- `build_runtime(..., chunking=None, code=_UNSET)`: `code`를 넘기면 그 값을 쓴다. 넘기지 않았고 `chunking`도 없으면 `code_chunking_from(settings)`을 읽는다.
  `chunking`을 명시했으면 꺼짐이다. 그래서 평가용 색인 준비(`devtools/eval_index.py:163-175`)는 바꾸지 않아도 늘 꺼짐이다(plan 재검토 N3).
- 켜짐일 때 `qk-index check` 교차 검사(`config/check.py`)는 문제가 있을 때만 항목을 만든다(`_generation_check`와 같은 방식).
  `config/check.py`는 질의 경로도 가져오므로 이 검사는 함수 안에서 `chunking.version`·`sync.keys`·`domain.keyword_rules`를 가져온다.
  또 INDEX 진입점에서 `QK_CODE_CHUNKING=on`일 때만 계산한다. 그래서 질의 경로에 `chunking`·`markdown_it`이 들어가지 않는다(plan 재검토 N2).
  - `CODE_LIMIT_OVER_CONTEXT_BUDGET`: `limit_tokens × 모델 bytes_per_token_estimate ÷ RetrievalSettings.bytes_per_token > QK_RETRIEVAL_CONTEXT_BUDGET`일 때(research R-03)
  - `CODE_INDEX_VERSION_UNREGISTERED`: 켜짐 설정으로 계산한 인덱스 버전이 `INDEX_KEYWORD_RULES`에 없을 때(research R-09, spec FR-030)
- `qk-index run`은 설정 검사를 통과하지 못하면 원본 호출·청킹·저장 전에 멈춘다(지금 순서 그대로). 그래서 대응표에 새 인덱스 버전을 더하기 전에는 환경값만으로 켜지지 않는다(spec US6-5).

## 5. chunk_code

```python
def chunk_code(body: str, *, location: str, settings: ChunkingSettings, code: CodeChunkingSettings) -> ChunkOutcome
```

자료 하나를 청킹하는 순수 함수다. 호출 전 거르기는 `chunk_screened`가 한다.

보장:

1. 같은 인자면 같은 결과다(spec FR-003). 자료원 종류·이름은 인자에 없다.
2. 줄 바꿈을 LF로 바꾸고 앞 BOM을 뺀 뒤 처리한다. 줄 번호는 원문 기준이다(spec FR-008). `document_title`은 `location`의 파일 이름이다.
3. `outcome == CHUNKED`이면 다음을 지킨다.
   - `drafts[i].chunk.ordinal == i`. 순서는 spec FR-012를 따른다.
   - 원문 청크(`locator["code"]["summary"] == False`): `"\n".join(원문줄[start-1:end]) == chunk.body`(spec FR-009).
     공백 아닌 원문 줄은 정확히 한 원문 청크의 줄 범위에 든다.
   - 요약 청크: 본문의 모든 줄이 `lines` 범위 안의 원문 줄과 같다. 시그니처 줄이 아닌 메서드 본문 줄은 없다(spec FR-013, SC-002).
   - `estimated_tokens(draft.embedding_text) ≤ code.limit_tokens`(spec FR-016~018).
   - `draft.embedding_text`와 `draft.chunk.search_text`는 `draft.search_header`로 시작한다(research R-07).
   - `draft.chunk.heading_path`는 spec FR-020 표의 심볼 경로다. `draft.chunk.chunking_version == code_chunking_version(code, settings)`.
   - QK-STO-001 `validate_chunks`를 통과한다.
4. 구문 해석 오류가 있으면 파일 전체를 대체 청킹하고 `PARSE_FALLBACK` 경고를 붙인다. 실패로 만들지 않는다(spec FR-019).
   Kotlin은 해석용 같은 길이 사본으로 해석한다(research R-01).
5. `EMPTY`·`FAILED`이면 `drafts == ()`다. 실패 유형은 `LINE_TOO_LONG`·`HEADER_TOO_LONG`·`PROCESSING_ERROR`다(spec FR-005·018).
6. 예외를 던지지 않는다. 내부 예외와 해석기 적재 실패는 `FAILED` + `PROCESSING_ERROR`다.

## 6. chunk_screened (바뀌는 점)

```python
def chunk_screened(
    passed: Iterable[ScreenedContent],
    settings: ChunkingSettings,
    *,
    code: CodeChunkingSettings | None = None,
) -> ChunkingResult
```

- `content_format == MARKDOWN`인 자료는 지금과 같이 `chunk_markdown`을 부른다. 결과는 한 글자도 바뀌지 않는다(spec FR-002, SC-008).
- `code`가 있고 코드 청킹 대상(spec FR-001)이면 `chunk_code`를 부른다. `code.model_version != settings.model_version`이면 시작 전에 `ValueError`다.
- 나머지는 `NOT_MARKDOWN`이다. `code is None`이면 `.java`·`.kt`도 여기에 들어가고, 해석기를 가져오지 않는다(spec US6-2).
- 요약: 결과가 하나 이상이면 `ChunkingSummary.from_results(results, chunking_version=index_chunking_version(settings, code), code_chunking_version=...)`다.
  결과가 없으면 지금처럼 인자 없이 부른다(research R-10, plan 재검토 N8). `sync/plan.py:216`도 같다.
- 기존 위치 인자 호출(`chunk_screened(passed, settings)`)은 그대로 동작한다.

## 7. 후속·연결 명세가 쓰는 방법

| 대상 | 쓰는 값 |
| --- | --- |
| QK-SYN-001 코드 | `SyncDependencies.code_chunking`(기본 `None`)을 받아 `version_for`로 문서별 변경을 판정한다. 인덱스 버전은 `index_chunking_version`·`metadata_schema_version`으로 계산하고 `IndexSpec`을 채운다. 나머지 저장·임베딩 흐름은 그대로다 |
| QK-EMB-001 | 바꿀 것 없음. 요약 청크를 포함한 모든 `embedding_text`가 캐시에 없으면 전송 직전 검사를 거친다(spec SC-009) |
| QK-RET-001·QK-GEN-001 | 바꿀 것 없음. `Provenance.locator["code"]`와 `heading_path`(심볼 경로)가 그대로 돌아온다 |
| QK-STO-002(켜는 변경) | `QK_CODE_CHUNKING=on`의 새 인덱스 버전을 `INDEX_KEYWORD_RULES`에 더하고 고정값 시험을 갱신한 뒤 생성·평가·활성화한다(spec FR-022·030) |
| 자료원별 식별 명세(초안 QK-SYN-005) | 같은 종류 자료원 두 개 이상을 받게 한다. 끝나야 코드 자료원을 켤 수 있다(spec FR-036) |
| QK-CHK-004 | `locator["code"]`의 `annotations`·`signature`·`symbol`과 `heading_path`로 컨트롤러·네트워크 호출을 잇는다 |

## 8. 텍스트 형식 (research R-07 보충, 2026-10-26 사용자 결정)

기존 `chunking/header.py`의 `search_text(header, body, rule)`와 `embedding_text(header, prefix, body)`를 그대로 다시 쓴다. 두 함수는 헤더와 나머지 사이에 빈 줄 하나(`"\n\n"`)를 넣는다.

| 값 | 형식 |
| --- | --- |
| 검색 헤더 | 첫 줄 `<위치> <언어>[ <패키지>]`, 둘째 줄 `<심볼 경로를 " > "로 이음> [<CodeChunkKind 값>][ <표시 이름>]`. 심볼 경로가 비면 둘째 줄은 `[<CodeChunkKind 값>]`. 끝 줄 바꿈 없음 |
| 패키지 생략 | `"/" + 패키지.replace(".", "/") + "/"`가 `"/" + 위치` 안에 있으면 첫 줄에서 ` <패키지>`를 뺀다 |
| 임베딩 입력 | `embedding_text(헤더, prefix, 본문)`. `prefix`는 맥락 줄과 (뒤 조각이면) 반복 줄을 순서대로 `"\n"`으로 이은 값이고, 없으면 `""` |
| 키워드 검색 텍스트 | `search_text(헤더, 맥락 + 본문, 규칙)`. `맥락 + 본문`은 맥락 줄이 있으면 `"\n".join(맥락 줄) + "\n" + 본문`, 없으면 본문 |

예: 메서드 청크(맥락 줄 2줄, 반복 줄 없음)의 임베딩 입력은 다음과 같다.

```text
src/main/java/com/x/OrderController.java java
OrderController > getOrder(Long) [METHOD]

@RequestMapping("/orders")
public class OrderController {
@GetMapping("/{id}")
public ResponseEntity<OrderResponse> getOrder(@PathVariable Long id) {
    return service.find(id);
}
```

파일 머리 청크의 둘째 줄은 `[FILE_HEAD]`다. 상한 때문에 나뉜 메서드의 뒤 조각은 맥락 줄 다음에 시그니처 줄을 반복한다. 형식 요약은 바깥 형식의 맥락 줄만 붙는다.
