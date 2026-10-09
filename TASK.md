# Task Contract: WBS 0.6 Workers AI 확인

> Generated at: `2026-10-09`
>
> 이 파일은 현재 작업 브랜치의 계약이다. 저장소 공통 정책은 `AGENTS.md`를 따른다.

## Work gate

- ClickUp 작업 ID / URL: 해당 없음: 초기 세팅 단계 예외. 진행 상태는 WBS 보드 0.6에서 관리
- 기능명세서 ID / 링크: 해당 없음: Phase 0 준비 작업(WBS 0.6)이라 명세 백로그 대상이 아님. 작업 정의는 `docs/sdd/roadmap.md` 3절
- 팀 스프린트 ID: `QELLO-S2026-W41`
- GitHub Issue: `#14`
- Branch: `docs/gh-14-workers-ai-spike`
- Base branch: `main`

## Objective

- Workers AI 임베딩·생성 모델이 설계대로 쓰일 수 있는지 확인하고, 청크 크기·일일 예산·ADR-009 결정에 쓸 수치를 `docs/sdd/research/spike-workers-ai.md`에 남긴다.

## Scope

- 임베딩: `@cf/google/embeddinggemma-300m`의 입력 한도, Neurons 단가, 질의·문서 접두 형식을 확인한다.
  `@cf/baai/bge-m3`, `@cf/qwen/qwen3-embedding-0.6b`와 같은 한국어 질의·문서 쌍으로 검색 순위를 비교한다.
- 생성: `@cf/qwen/qwen3-30b-a3b-fp8`(추론 끔), `@cf/ibm-granite/granite-4.0-h-micro`,
  `@cf/mistralai/mistral-small-3.1-24b-instruct`로 한국어 질문 5개에 답하게 하고 응답 시간, 토큰 수, Neurons,
  출처 표시, 확인 불가 응답, 문맥 속 지시문 무시 여부를 비교한다.
- 무료 할당 초과 시 동작은 공식 문서로 확인한다. 일부러 한도를 넘기지 않는다.
- 측정은 에이전트가 만든 일회성 스크립트로 한다. 스크립트와 원본 결과 JSON은 저장소에 두지 않고, 측정 방법·질문 세트·답변 원문을
  `spike-workers-ai.md`에 적는다.

## Explicit exclusions

- 팀 자료(저장소 문서, ClickUp 등)를 Workers AI로 보내는 일. 질문과 문맥은 에이전트가 만든 합성 문서만 쓴다.
- Workers Paid 전환, 결제 수단 등록 등 유료 과금이 시작되는 설정 변경.
- 무료 할당을 일부러 소진해 초과 동작을 재현하는 일.
- 수집·검색·봇 코드 작성, ADR-002·009 결정 자체(0.9).
- `AGENTS.md`, `CLAUDE.md`, `.claude/**`, `docs/sdd/roadmap.md` 수정. 고칠 점은 `spike-workers-ai.md`에 적는다.
- 공유 DB 초기화, 인덱스 전체 삭제, 유료 과금 설정 변경은 별도 승인 없이 하지 않는다.
- 비밀값, 토큰, `.env` 값, 계정 ID, 비공개 원문은 기록하지 않는다.

## Data and cost impact

- 새로 읽는 자료원: 해당 없음.
- 외부 API로 보내는 데이터: 합성 한국어 문서·질문만 Cloudflare Workers AI로 보낸다. Cloudflare는 Workers AI 입력·출력을
  모델 학습에 쓰지 않는다고 밝힌다(`spike-workers-ai.md` 출처).
- 예상 임베딩·생성 호출량과 무료 한도 대비: 약 2,000 Neurons 이하(일일 무료 10,000의 20%). 내역은 임베딩 입력 한도 탐색 최대 약 800
  (embeddinggemma 단가를 1M 토큰당 20,000으로 보수적으로 가정), 임베딩 검색 비교 약 200, bge-m3·qwen3 한도 확인 약 130,
  생성 15회 약 710. 스크립트는 추정 누적 3,000 Neurons에 이르거나 429를 받으면 멈춘다. Workers Free 플랜이라 과금되지 않는다.
- 인덱스 버전 변경: 없음

## Ownership

| Area (paths) | Owner | Required review |
| --- | --- | --- |
| `docs/sdd/research/spike-workers-ai.md` | 확인 필요 | 사람 리뷰 |
| `TASK.md` | 확인 필요 | 사람 리뷰 |

## Existing user-owned changes

- 2026-10-09 브랜치 생성 시 `git status --short` 결과: 변경 없음

## Validation

```bash
python scripts/preflight.py
git diff --check
grep -rnE 'github_pat_[A-Za-z0-9_]{20,}|cfat_[A-Za-z0-9_-]{20,}|[0-9a-f]{32}' docs TASK.md   # 결과가 없어야 한다. 토큰·32자리 16진수(계정 ID 형식)
```

## Completion criteria

- `spike-workers-ai.md`에 embeddinggemma 입력 한도, Neurons 단가, 접두 형식, 무료 할당 초과 시 동작이 근거(공식 문서 또는 측정 조건)와 함께 있다. 리뷰로 확인한다.
- 임베딩 3종 한국어 검색 비교와 생성 후보 3종 한국어 답변 비교가 모델, 질문 세트, 표본 수, 사용 Neurons와 함께 있다. 리뷰와 문서 부록(질문 세트, 답변 원문)으로 확인한다.
- 측정에 쓴 Neurons가 무료 할당 안이었고 문서에 토큰·계정 식별자가 없다. 위 검증 명령과 리뷰로 확인한다.

## Decisions

- 2026-10-09 사용자 결정: 0.5와 같이 초기 세팅 단계 예외로 ClickUp 작업 없이 진행하고 GitHub Issue(#14)를 만든다.
- 2026-10-09 사용자 결정: Workers AI 호출은 에이전트가 실행한다. 서브셸에서 `.env`를 불러 쓰고 토큰·계정 ID는 출력하거나 기록하지 않는다.
- 2026-10-09 사용자 확인: Cloudflare 계정은 Workers Free 플랜이다.
- 2026-10-09 사용자 결정: 하루 질문은 많아야 50건이고, 한국어 지원 필수, 빠른 응답, 무료(Workers Free 할당 안)를 조건으로 한다.
  이 조건으로 생성 후보를 한국어를 공식 문서에 명시한 모델로 좁혔다. Llama 계열(한국어 공식 미지원), gpt-oss(지원 언어 미명시,
  50건이면 할당의 약 89%. 입력 3,000·출력 1,200토큰 가정), gemma-4(한국어 명시 없음)는 뺐다.
- 2026-10-09 사용자 선택: `@cf/baai/bge-m3`를 비교 대상에 넣는다. 임베딩 모델이므로 임베딩 비교에 넣었다(에이전트 해석).
- 2026-10-09 사용자 결정: 생성 모델로 `@cf/qwen/qwen3-30b-a3b-fp8`(추론 끔)을 쓴다. 근거는 `spike-workers-ai.md` 4·5.2절이다.
  ADR-009 결정 기록은 0.9에서 남기고, 답변 평가(QK-EVL-002)에서 다시 확인한다. 임베딩 모델(ADR-002)은 아직 정하지 않았다.
- 2026-10-09 사용자 결정: 커밋에는 `TASK.md`와 `spike-workers-ai.md`만 넣는다. 측정 스크립트와 원본 결과 JSON은 커밋하지 않는다.
