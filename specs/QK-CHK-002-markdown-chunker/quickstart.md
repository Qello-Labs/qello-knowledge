# Quickstart: QK-CHK-002 검증 안내

구현이 명세를 만족하는지 확인하는 순서다. 1~3절은 외부 호출 0건이고, 4절은 사람이 실행하는 관찰(GitHub 약 83회, 0 Neurons)이다.

## 0. 준비

```bash
uv sync --locked          # dev 그룹에 markdown-it-py==4.2.0이 들어 있다(research R-01)
```

## 1. 단위 시험 (외부 호출 0건)

```bash
uv run pytest tests/unit/chunking -q
uv run pytest tests/unit/test_boundaries.py -q
```

| 시험 묶음 | 확인하는 것 | spec |
| --- | --- | --- |
| 기대값 시험(`tests/fixtures/chunking/*.md` + 사람이 쓴 기대 JSON) | 결과 종류·실패 유형, 청크별 순서·줄 범위·제목 경로·키워드 검색용 텍스트·임베딩 입력 텍스트(뒤 조각 반복 머리글 포함), 목록 항목 경계 보존, 여러 줄 밑줄형 제목 | SC-001, US1~4 |
| 반복·순서 | 같은 묶음을 두 번, 처리 순서를 섞어 한 번 더 청킹해 자료별 결과 비교 | SC-001 |
| 정규화 | CRLF·LF·CR만 다른 본문, 앞 BOM 유무 → 같은 결과. 탭·줄 끝 공백은 본문에 그대로 | FR-007, US1 시나리오 7 |
| 원문 대조·줄 덮기·저장 검증 | 본문 = 줄 범위 원문, 공백 아닌 줄 정확히 한 번, 모든 절에 청크, `validate_chunks` 통과 | SC-002 |
| 크기 | 작은 시험용 상한으로 3배 문서·큰 절·큰 표·큰 코드·큰 목록(항목은 상한 이하)·큰 목록 항목 안의 작은 하위 항목·표·코드(재귀 보존)·여러 문단 인용(가운데 `>` 줄 덮기)·목표~상한 사이 문단. 줄 길이 초과·헤더 길이 초과 경계값, 반복 머리글이 없으면 통과하고 있으면 실패하는 표·코드 줄 | SC-003, FR-015·016 |
| 국소성 | 절 본문만 고친 판, 문서 제목이 아닌 제목 줄만 고친 판, 문서 제목을 고친 판 | SC-004 |
| 구조 | 펜스·들여쓴 코드·인용·목록·HTML 안의 제목 모양 줄, 앞머리 메타데이터, 표 셀 수 6사례·펜스 닫힘 16사례(research R-11), 언어 표시만 다른 두 문서 | SC-005 |
| 헤더 | 제목 없는 문서, 본문 없는 상위 제목, 원본 제목 우선순위, 꾸밈 제거(줄바꿈 → 공백), 중복 제거 | SC-006 |
| 실패 격리 | 실패 주입(줄·헤더 길이, 처리 오류), Markdown 아닌 자료. 결과·경고·요약·측정 출력 문자열과 `caplog`에 시험 본문의 표지 문자열이 없음 | SC-007 |
| 자료원 독립 | 종류가 다른 두 가짜 자료원에 같은 본문 | SC-008 |
| 버전 | 첫 값 `chk-md-20d966f730bb` 고정, 설정 항목별·판수별 변경 → 버전 변경, 같은 설정 → 같은 값, 경고 판정만 변경 → 같은 값 | SC-009 |
| 요약 | 요약 수치(결과별 `split_blocks` 합, 낮은 쪽 중앙값 포함) = 결과를 직접 센 값 | SC-010 |
| 성능 회귀 | 시드 `20261021` 합성 문서 79개(입력 SHA-256·총 바이트 고정) 청킹 10초 이하. 완료 판정은 3절(research R-12) | SC-011 |
| 경계 | `domain`·`ports`·`embedding`·`query`가 `chunking`·`markdown_it`를 가져오지 않는다 | research R-10 |

## 2. 기본 검증 (AGENTS.md 7절)

```bash
python scripts/preflight.py
git diff --check
uv run ruff check .
uv run ruff format --check .
uv run qk-dev db up
QK_REQUIRE_LOCALDB=1 uv run pytest
```

## 3. SC-011 완료 판정 (고정 입력, 외부 호출 0건)

대상 저장소 로컬 사본이 필요하다. research R-12의 고정 입력(커밋 `6aeccd0`, 79개, 1,017,913바이트)을 청킹하고 소요 시간을 잰다.

```bash
uv run python specs/QK-CHK-002-markdown-chunker/measurement/measure_inputs.py \
  --repo <대상 저장소 로컬 사본> --commit 6aeccd039b825dcd7a2b6c046a34ef72089a1f78 --source dnd-backend-docs \
  --blocked docs/superpowers/plans/2026-09-10-codex-agents-token-optimization.md --time-chunking
```

출력이 `chunking.files == 79`, `chunking.total_bytes == 1017913`, `chunking.by_outcome == {"CHUNKED": 79}`, `chunking.chunk_count > 0`,
`chunking.elapsed_seconds ≤ 10`(반올림하지 않은 값)이면 통과다. 장비 정보도 함께 기록한다.

## 4. 실제 대상 문서 관찰 (사람 실행)

`.env`에 `GITHUB_API_TOKEN`이 있어야 한다. 원본 호출은 기존 수집 측정과 같다(약 83회, 시간당 5,000회 한도 안). 저장·임베딩 없음, 0 Neurons.

```bash
uv run qk-dev source measure --name dnd-backend-docs --chunk
uv run qk-dev source measure --name dnd-backend-docs --chunk --json   # 기록용
```

관찰값이다(research R-12). 실행 시점 `main` 기준이라 문서 수가 커밋 `6aeccd0`의 79개와 다를 수 있다. 그 커밋과 같다면 기대 결과는:

- `CHUNKED` 79, `FAILED` 0(줄 길이 초과 0), 예상 토큰 최대 ≤ 2,800.
- 본문 없는 제목 절이 약 73개 있으므로 예상 토큰이 아주 작은 청크가 있다.
- 출력의 커밋·환경·`chunking.elapsed_seconds`를 기록한다.

plan 측정(research R-02·R-03)을 다시 내려면 `specs/QK-CHK-002-markdown-chunker/measurement/measure_inputs.py` 머리말의 명령을 쓴다(대상 저장소 로컬 사본 필요).

결과는 필요하면 `docs/sdd/research/github-source-measurement.md`에 측정 조건(커밋, 설정, 청킹 규칙 버전, 장비)과 함께 덧붙인다(C-13).
문서 경로 외의 원문은 적지 않는다.
