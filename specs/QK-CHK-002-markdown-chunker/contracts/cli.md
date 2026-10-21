# Contract: CLI

## qk-dev source measure --chunk (기존 명령에 선택 인자 추가)

```text
qk-dev source measure --name <자료원> [--chunk] [--json] [기존 인자]
```

- `--chunk`가 없으면 지금 동작과 출력이 그대로다(기존 시험이 깨지지 않는다).
- `--chunk`가 있으면 보안 필터 통과 자료(`ScreenResult.passed`)를 기본 `ChunkingSettings`로 `chunk_screened`에 넘기고, 측정 출력에 `chunking` 항목을 더한다.
  원본 호출은 `--chunk` 없을 때와 같다(외부 호출을 더하지 않는다). 저장·임베딩은 하지 않는다.
- 출력에 문서 본문, 청크 본문, 검색 헤더, 임베딩 입력 텍스트를 넣지 않는다. 위치는 QK-SEC-001 기록 출력 규칙(`safe_text`, `FieldKind.PATH`)을 거친다.

사람용 출력 추가 줄(값은 예시):

```text
  청킹      chk-md-0123456789ab target=512 limit=2800, 소요 0.842초
  청킹 결과 {"CHUNKED": 79} 청크 1302개, 예상 토큰 min=9 median=168 max=2731, 줄 단위로 나뉜 블록 3개
  청킹 실패 docs/example.md  LINE_TOO_LONG
  구조 경고 docs/example.md:42  TABLE_CELL_MISMATCH
```

`--json`이면 `chunking` 객체를 더한다.

```json
{
  "chunking": {
    "chunking_version": "chk-md-0123456789ab",
    "settings": {"model_version": "@cf/baai/bge-m3", "target_tokens": 512, "limit_tokens": 2800},
    "elapsed_seconds": 0.842,
    "summary": {"by_outcome": {}, "chunk_count": 0, "by_failure": {}, "by_warning": {},
                "tokens_min": null, "tokens_median": null, "tokens_max": null, "split_blocks": 0},
    "failures": [{"path": "<safe_text>", "failure": "LINE_TOO_LONG"}],
    "warnings": [{"path": "<safe_text>", "line": 42, "kind": "TABLE_CELL_MISMATCH"}]
  }
}
```

- 종료 코드는 기존 규칙을 따른다(수집 측정이 `ok`가 아니면 1). 청킹 실패·경고가 있어도 종료 코드를 바꾸지 않는다. 측정 기록용이기 때문이다.
- `elapsed_seconds`는 `chunk_screened` 호출 구간만 잰다(수집 시간 제외).
