# Data Model: QK-CHK-002 Markdown 청커·검색 헤더

모든 타입은 `src/qello_knowledge/domain/chunking.py`의 불변 dataclass·StrEnum이다(표준 라이브러리만, research R-10).
저장 스키마와 `ChunkInput`(QK-STO-001)은 바꾸지 않는다. 새 테이블·마이그레이션은 없다.

## 입력

| 출처 | 쓰는 값 | 규칙 |
| --- | --- | --- |
| `ScreenedContent.content: SourceContent` | `body`, `content_format`, `location`, `title` | 본문·위치·형식은 본문 조회 결과 기준(spec FR-008) |
| `ScreenedContent.item: SourceItem` | `source_name`, `source_id`, `title` | 제목은 `content.title`, 없으면 `item.title`(QK-ING-001 data-model, spec FR-017) |
| `ScreenedContent.access_scope`, `rules_version` | 그대로 결과에 남긴다 | 청킹 결과는 바꾸지 않는다 |

`content_format != MARKDOWN`이면 `NOT_MARKDOWN` 결과다(spec FR-001).

## ChunkingSettings

| 필드 | 타입 | 기본값 | 검증 |
| --- | --- | --- | --- |
| `model_version` | str | `@cf/baai/bge-m3` | `domain.embedding.MODELS`에 있어야 한다 |
| `target_tokens` | int | 512 (research R-04) | 1 이상, `limit_tokens` 이하 |
| `limit_tokens` | int | 2,800 (research R-03) | `limit_tokens × bytes_per_token_estimate ÷ WORST_BYTES_PER_TOKEN ≤ max_input_tokens` |

- `WORST_BYTES_PER_TOKEN = 1.2`(상수, research R-03). 검증 실패는 `ValueError`로, 청킹을 시작하기 전에 멈춘다.
- 예상 토큰은 `embedding.estimate.estimated_tokens(text, MODELS[model_version])`와 같은 계산이다(spec FR-013).

## 상태 값

| 타입 | 값 | 뜻 |
| --- | --- | --- |
| `ChunkOutcomeKind` | `CHUNKED`, `EMPTY`, `NOT_MARKDOWN`, `FAILED` | 자료 하나의 결과(spec FR-004) |
| `ChunkFailureKind` | `LINE_TOO_LONG`, `HEADER_TOO_LONG`, `PROCESSING_ERROR` | `FAILED`일 때만 |
| `StructureWarningKind` | `TABLE_CELL_MISMATCH`, `UNCLOSED_FENCE` | `CHUNKED` 결과에만 붙는다(spec FR-024) |

## StructureWarning

| 필드 | 타입 | 설명 |
| --- | --- | --- |
| `kind` | StructureWarningKind | |
| `line` | int | 원문 줄 번호(1부터) |

## ChunkDraft

| 필드 | 타입 | 설명 |
| --- | --- | --- |
| `chunk` | `ChunkInput` | QK-STO-001 그대로. `ordinal`(0부터 연속), `locator`, `body`, `search_text`, `chunking_version`, `heading_path` |
| `search_header` | str | 두 줄(research R-09) |
| `embedding_text` | str | 검색 헤더 + 빈 줄 + (반복 머리글) + 본문. 저장하지 않는다(spec FR-019) |

- `locator = {"path": <본문 조회 위치>, "lines": [시작, 끝]}`(양 끝 포함, QK-STO-001 data-model 예시와 같은 모양).
- `body`는 줄 범위 원문 그대로. `search_text` = `search_header + "\n\n" + body`. `embedding` 필드는 비운다(QK-SYN-001이 채운다).
- 불변식: `estimated_tokens(embedding_text) ≤ limit_tokens`. 같은 절에서 나온 청크는 `heading_path`가 같다.

## ChunkedContent (자료 하나의 결과)

| 필드 | 타입 | 설명 |
| --- | --- | --- |
| `screened` | `ScreenedContent` | 입력 그대로(`repr` 제외). QK-SYN-001이 원본 자료 항목을 만들 때 쓴다 |
| `outcome` | ChunkOutcomeKind | |
| `document_title` | str \| None | spec FR-017 결과. `NOT_MARKDOWN`이면 `None` |
| `drafts` | tuple[ChunkDraft, ...] | `CHUNKED`일 때만 1개 이상, 나머지는 빈 튜플 |
| `warnings` | tuple[StructureWarning, ...] | 줄 번호 순 |
| `failure` | ChunkFailureKind \| None | `FAILED`일 때만 |
| `split_blocks` | int | 상한 때문에 자식·줄 단위로 나뉜 블록 수(research R-08). `CHUNKED`가 아니면 0(실패 도중의 시도는 세지 않는다) |
| `chunking_version` | str | 결과마다 같은 값 |

- 불변식: `FAILED`·`EMPTY`·`NOT_MARKDOWN`이면 `drafts == ()`(spec FR-004, SC-007).
- 예외는 밖으로 던지지 않는다. 예상하지 못한 예외는 `FAILED` + `PROCESSING_ERROR`가 되고 다음 자료로 넘어간다(spec FR-005). 예외 문구는 남기지 않는다.

## ChunkingSummary

| 필드 | 타입 | 설명 |
| --- | --- | --- |
| `chunking_version` | str | |
| `by_outcome` | Mapping[ChunkOutcomeKind, int] | |
| `chunk_count` | int | |
| `by_failure` | Mapping[ChunkFailureKind, int] | |
| `by_warning` | Mapping[StructureWarningKind, int] | |
| `tokens_min`, `tokens_median`, `tokens_max` | int \| None | 모든 청크 임베딩 입력 텍스트의 예상 토큰. 중앙값은 낮은 쪽 중앙값(`statistics.median_low`)이라 정수다. 청크가 없으면 `None` |
| `split_blocks` | int | 결과별 `split_blocks`의 합 |

- `ChunkingSummary.from_results(results)`로만 만든다. 그래서 요약은 자료별 결과를 센 값과 같다(spec SC-010). 식별자·본문을 담지 않는다.

## ChunkingResult

| 필드 | 타입 |
| --- | --- |
| `results` | tuple[ChunkedContent, ...] (입력 순서) |
| `summary` | ChunkingSummary |

## 청킹 규칙 버전

`chk-md-` + 12자리 16진수(research R-07). `chunking_version(settings) -> str`은 같은 설정이면 같은 값을 돌려준다. 재료는 규칙 판수, 설정, 해석기 이름·버전·설정,
헤더·키워드 텍스트·임베딩 입력 형식 판수다. 구조 경고 판정은 재료가 아니다.

## 내부 중간값 (`chunking/` 안에서만)

| 이름 | 내용 |
| --- | --- |
| `Block` | `start`, `end`(0부터, 끝 제외), `kind`(heading·paragraph·list·list_item·blockquote·table·fence·code·html·hr·raw·front_matter), 제목이면 `level`, `text`, 표면 머리글 두 줄·펜스면 여는 줄(반복 머리글), `children`(바로 아래 자식 `Block`들의 나무. 목록 → 항목, 항목·인용 → 안쪽 블록. research R-05) |
| `Section` | `heading_path`, `blocks` |

이 둘은 공개 계약이 아니다. 시험은 공개 진입점(contracts/chunker.md)으로 한다.
