# Contract: 자료원 어댑터

새 자료원은 이 계약만 구현하면 동기화·보안 필터·청커를 고치지 않고 파이프라인에 붙는다(US1). 타입 정의는 [data-model.md](../data-model.md)에 있다.

## Protocol (`qello_knowledge.ports.source`)

```python
class SourceAdapter(Protocol):
    kind: str

    def list_page(self, session: SourceSession, config: SourceConfig, cursor: str | None) -> ListPage: ...
    def fetch_content(self, session: SourceSession, config: SourceConfig, item: SourceItem) -> SourceContent: ...
    def classify(self, response: SourceResponse) -> ResponseClass: ...
    def rate_limit_hint(self, response: SourceResponse) -> RateLimitHint | None: ...


class SourceTransport(Protocol):
    def send(self, request: SourceRequest) -> SourceResponse: ...   # 요청 하나. 리다이렉트를 따라가지 않는다


class SourceSession(Protocol):
    def send(self, request: SourceRequest) -> SourceResponse: ...   # 어댑터가 쓰는 유일한 요청 창구
```

`SourceSession`의 구현은 `sources/session.py`에 있고, 어댑터는 Protocol만 안다.

## 어댑터가 지킬 것

1. 원본에 요청할 때는 `session.send()`만 쓴다. 전송·소켓·HTTP 라이브러리를 직접 부르지 않는다.
2. `send()` 한 번은 원본 요청 한 번이다. 세션이 이 수로 한도를 센다.
3. `GET`·`HEAD`만 보낸다. 그 밖의 메서드는 세션이 `ReadOnlyViolation`으로 막는다(C-09).
4. 입력과 출력에 원본 SDK·HTTP 라이브러리 타입을 쓰지 않는다. `domain/source.py` 타입만 쓴다(C-06, FR-004).
5. `list_page()`는 한 페이지만 돌려준다. 페이지 순회, 중복 제거, 포함·제외 패턴 적용은 공통 수집 함수가 한다.
6. `change_key`를 반드시 채운다. 원본 버전·수정 시각이 없으면 본문을 받아 내용 해시로 채운다.
7. 권한 정보를 원본이 주지 않으면 `AccessInfo(UNKNOWN)`이다. 추측해서 채우지 않는다.
8. 응답 형식이 예상과 다르면 `InvalidResponse`를 낸다. 빠진 필드를 기본값으로 채우지 않는다.
9. `content_hash`·`fetched_at`은 비워 둔다. 세션이 채운다.
10. 예외는 세션이 낸 것(`SourceFailure`)과 `InvalidResponse`만 밖으로 보낸다.
11. 로그·예외 메시지에 토큰, 요청 헤더, 응답 본문, URL 질의 문자열을 넣지 않는다.

## 세션이 하는 것

| 일 | 규칙 | 요구사항 |
| --- | --- | --- |
| 읽기 전용 강제 | `GET`·`HEAD` 밖이면 보내기 전에 `ReadOnlyViolation` | FR-001, SC-002 |
| 호출 한도 | 분당(선택: 초당) 창, 실행당 상한, 원본 한도 힌트 중 엄격한 쪽 | FR-014, FR-015 |
| 대기 상한 | 기다릴 시간 > `max_wait_seconds`면 `RunStopped(WAIT_TOO_LONG)` | FR-016 |
| 재시도 | `adapter.classify()`가 일시적이면 백오프 후 재시도, 상한 소진 시 `SourceFailure(TRANSIENT)` | FR-017, FR-018 |
| 인증 실패 | 재시도 없이 `RunStopped(AUTH_FAILED)` | FR-020 |
| 리다이렉트 | 3xx의 `Location` 호스트가 `allowed_hosts`에 있으면 최대 3번 따라감, 아니면 `SourceFailure(REDIRECT_BLOCKED)` | FR-022 |
| 크기 상한 | `request.max_bytes`를 `max_content_bytes`로 채우고, 응답이 잘렸으면 `SourceFailure(SIZE_EXCEEDED)` | Edge Cases |
| 해시·시각 | `SourceContent`의 `content_hash`·`fetched_at`을 채운다 | FR-003 |

## 공통 수집 함수 (`sources/collect.py`)

```python
def list_all(adapter, config, session) -> Listing
def fetch_contents(adapter, config, session, items) -> FetchResult
```

- `list_all`: 커서가 `None`이 될 때까지 `list_page()`를 부른다. `source_id`로 중복을 버리고, 포함·제외 패턴(`location` 기준)을 적용한다.
  페이지가 실패하거나 실행이 멈추면 `complete=False`로 지금까지의 항목을 돌려준다.
- `fetch_contents`: 항목마다 `fetch_content()`를 부른다. `size_bytes`가 상한을 넘으면 요청 없이 `SIZE_EXCEEDED`로 기록한다.
  `SourceFailure`는 그 항목에만 기록하고 다음 항목으로 넘어간다(C-08). `RunStopped`면 남은 항목을 `SKIPPED`로 남기고 멈춘다.
- 비활성 자료원은 부르지 않는다. 호출하는 쪽(QK-SYN-001)이 `enabled`를 보고 건너뛴다.

## 공통 계약 테스트

`tests/contract/source_adapter_contract.py`의 `SourceAdapterContract`를 상속하고 fixture 세 개(`adapter`, `transport`, `config`)를 구현한다.
검사는 저장된 응답으로만 돌고 실제 원본을 부르지 않는다(FR-006, C-12).

| 검사 | 근거 |
| --- | --- |
| 목록 항목마다 필수 필드가 공통 형식으로 채워진다. 권한이 없으면 `UNKNOWN` | US1-1, FR-002 |
| 본문 조회 결과에 본문·내용 형식·원본 버전·위치가 있다 | US1-2, FR-003 |
| 수정 시각이 없으면 `change_key_kind == CONTENT_HASH` | US1-3 |
| 여러 페이지 목록에서 `source_id` 중복이 없다 | US1-4, FR-005 |
| 기록된 요청의 메서드가 모두 `GET`·`HEAD`다 | US1-5, FR-006, SC-002 |
| 입력·출력 타입이 `domain` 모듈에서 온다 | FR-004 |
| 형식이 다른 응답은 `InvalidResponse`이고 다음 항목이 처리된다 | Edge Cases |
