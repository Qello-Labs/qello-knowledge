# Contract: 게이트 정책 `qk-sto-002-gate-policy/v1`

**Spec**: FR-012, FR-015, FR-017, D3, D4 | **Research**: R-09, R-10

## 1. 위치와 고정

- 파일: `eval/gate_policies/<정책 ID>/v<버전>.toml`. 정책 ID는 `^[a-z0-9][a-z0-9-]{1,62}$`, 버전은 1 이상 정수이고 파일 이름의 버전과 `version`이 같다.
- 지문: 파일 바이트의 SHA-256(16진수 64자).
- 값(허용 하락, 가드레일, 최소 판정 질문 수, 토크나이저)은 사람이 정하고, 측정 전에 리뷰를 거쳐 `main`에 병합한다. 정책 커밋은 평가 코드·측정 결과·후보 설정 변경과 다른 커밋이다.
- 병합된 파일은 고치지 않는다. 바꾸려면 `v<버전+1>.toml`을 더한다. 판정과 활성화는 R-09 방법으로 병합 여부·내용 동일·최신 여부를 확인한다.

## 2. 형식

```toml
schema = "qk-sto-002-gate-policy/v1"
id = "kw-index-idsplit-rollout"   # 정책 ID
version = 1
mode = "hybrid"                    # 판정 방식. vector·keyword·hybrid 가운데 하나, 기본 hybrid

[tokenizers]                        # 기준·후보 평가 대상의 키워드 색인 토크나이저(FR-033)
baseline = "TokenBigramSplitSymbol"
candidate = "TokenBigramSplitSymbol"

[search]                            # 요청 단위 검색 설정. 빠지면 RetrievalSettings() 기본값으로 채운다
query_rule = "kw-query-v1"
candidates = 20
rrf_k = 60

[[sets]]                            # 필수 질문 세트. 1개 이상
id = "qk-evl-001-golden"
version = 2
fingerprint = "<세트 파일 SHA-256>"
min_judged = 20                     # 최소 판정 질문 수(FR-015 (9))
max_drop = { recall_at_5 = "0", mrr = "0.02" }   # 허용 하락(≥ 0). 통과 조건: 후보 − 기준 ≥ −max_drop

[[sets]]
id = "qk-evl-001-identifiers"
version = 1
fingerprint = "<세트 파일 SHA-256>"
min_judged = 60
max_drop = { recall_at_5 = "0.0125", mrr = "0.02" }

[[guardrails]]                      # 0개 이상. kind는 G1·G2·G3
kind = "G1"                         # 기준 정상·후보 비정상 판정 질문 수 ≤ limit
set = "qk-evl-001-golden"
limit = "0"

[[guardrails]]
kind = "G2"                         # 식별자 세트 Precision@5 하락 ≤ limit
set = "qk-evl-001-identifiers"
mode = "keyword"
limit = "0"

[[guardrails]]
kind = "G3"                         # 키워드 전용 상한 도달 비율 증가 ≤ limit
set = "qk-evl-001-identifiers"
limit = "0.0125"
```

- 수치(`max_drop`, `limit`)는 소수 문자열이고 `Fraction`으로 읽는다. 음수, 지수 표기, 빈 문자열은 거부한다.
- G1의 방식은 정책 `mode`, G3의 방식은 `keyword`다(다른 값을 주면 거부). G1~G3의 `set`은 `[[sets]]` 가운데 하나다.
- 가드레일 값은 판정 질문 집합으로 계산한다(research R-10 5단계). 후보 결과가 비정상인 질문은 Precision@5 0, 상한 도달로 센다(후보에게 가장 나쁜 값). 가드레일 판정 질문이 0개면 판정 불가 `too_few_judged`다.
- 위 수치는 형식 예시다. 운영 정책 값은 사람이 정한다(TASK.md 제외 범위).
- 모르는 키가 있으면 거부한다. `tomllib`가 중복 키를 거부한다.

## 3. 검증 오류 이름

`policy_toml_invalid`, `policy_schema`, `policy_id`, `policy_version`, `policy_path_version`, `policy_mode`, `policy_no_sets`, `policy_set_duplicate`, `policy_number`,
`policy_min_judged`, `policy_guardrail_kind`, `policy_guardrail_set`, `policy_guardrail_mode`, `policy_tokenizer`, `policy_search`, `policy_unknown_key`.
게이트 명령은 정책 검증 오류가 있으면 기록을 쓰지 않고 종료 2로 멈춘다([cli.md](cli.md) 6절).
