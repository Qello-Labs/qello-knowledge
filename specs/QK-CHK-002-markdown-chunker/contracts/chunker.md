# Contract: 청커 진입점

모듈: `qello_knowledge.chunking`(해석기는 `chunking/blocks.py`에서만 가져온다). 타입은 [data-model.md](../data-model.md).
외부 호출, 저장, 로그 출력이 없다(spec FR-003, FR-006).

## chunking_version

```python
def chunking_version(settings: ChunkingSettings) -> str
```

- `chk-md-` + 12자리 16진수. 같은 설정이면 같은 값이다(research R-07).
- 청크 결과에 영향을 주는 설정·규칙 판수가 바뀌면 값이 바뀐다. 구조 경고 판정은 영향을 주지 않는다(spec FR-012, FR-024, SC-009).

## chunk_markdown

```python
def chunk_markdown(
    body: str,
    *,
    location: str,
    source_title: str | None,
    settings: ChunkingSettings,
) -> ChunkOutcome
```

자료 하나를 청킹하는 순수 함수다. `ChunkOutcome`은 `ChunkedContent`에서 `screened`를 뺀 값(`outcome`, `document_title`, `drafts`, `warnings`,
`failure`, `split_blocks`, `chunking_version`)이다.

보장:

1. 같은 인자면 같은 결과다(spec FR-002). 자료원 종류·이름은 인자에 없다.
2. `outcome == CHUNKED`이면
   - `drafts[i].chunk.ordinal == i`, 원문 순서(FR-010).
   - `"\n".join(원문줄[start-1:end]) == chunk.body`(`locator["lines"] == [start, end]`, FR-008).
   - 공백 아닌 원문 줄은 정확히 한 청크의 줄 범위에 든다(FR-009). 모든 절은 청크 1개 이상이다(FR-011).
   - 상한 이하인 블록은 어느 깊이에 있든(하위 목록 항목, 목록 항목 안 표·코드, 인용 안 블록 포함) 두 청크에 걸치지 않는다(FR-016, research R-08).
   - `estimated_tokens(draft.embedding_text) ≤ settings.limit_tokens`(FR-013).
   - `draft.embedding_text`와 `draft.chunk.search_text`는 `draft.search_header`로 시작한다(FR-019, FR-020).
   - `draft.chunk.chunking_version == chunking_version(settings)`.
   - QK-STO-001 `validate_chunks(source_version, chunks)`를 통과한다.
3. `outcome`이 `EMPTY`·`NOT_MARKDOWN`·`FAILED`이면 `drafts == ()`.
4. 예외를 던지지 않는다. 내부 예외는 `FAILED` + `PROCESSING_ERROR`다. 단, `settings`가 검증을 통과하지 못하면 호출 전에 `ValueError`다.

`body`가 Markdown인지는 호출하는 쪽이 정한다. `chunk_screened`가 `content_format`으로 거른다.

## chunk_screened

```python
def chunk_screened(
    passed: Iterable[ScreenedContent],
    settings: ChunkingSettings,
) -> ChunkingResult
```

- QK-SEC-001 `ScreenResult.passed`를 그대로 받는다(spec FR-001).
- 자료마다 `content_format != MARKDOWN`이면 `NOT_MARKDOWN`, 아니면 `chunk_markdown(content.body, location=content.location,
  source_title=content.title or item.title, settings=settings)`의 결과에 `screened`를 붙인다.
- 한 자료의 실패가 다른 자료를 멈추지 않는다(FR-005). `results`는 입력 순서다.
- `summary = ChunkingSummary.from_results(results)`(FR-027, SC-010).

## 후속 명세가 쓰는 방법

| 명세 | 쓰는 값 |
| --- | --- |
| QK-SYN-001 | `results[i].screened`로 원본 자료 항목을, `drafts[j].chunk`를 저장하고 `drafts[j].embedding_text`를 QK-EMB-001 `EmbedInput.text`로 넘긴다. `EMPTY`·`FAILED` 자료의 이전 청크 처리, 실행 기록에 `summary`를 넣는 일은 QK-SYN-001이 정한다 |
| QK-EMB-001 | 입력 텍스트만 받는다. 청커를 모른다. 한도 초과는 지금처럼 "입력 한도 초과"로 알린다 |
| QK-RET-001 | 저장된 `heading_path`로 상위 절, `search_text`로 키워드 검색. 같은 제목 경로 중복의 상위 절 조회 한계(spec Edge Cases)를 다룬다 |
