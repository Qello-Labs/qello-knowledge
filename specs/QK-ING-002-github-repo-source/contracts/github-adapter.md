# Contract: GitHub 저장소 파일 어댑터와 실제 전송

QK-ING-001 [contracts/source-adapter.md](../../QK-ING-001-source-adapter-contract/contracts/source-adapter.md)의 `SourceAdapter`·`SourceTransport`를 구현한다.
결정 근거는 [research.md](../research.md) R-01~R-08.

## `GitHubRepoFilesAdapter` (`adapters/github.py`)

`kind = "github_repo_files"`. 진단용 `last_snapshot` 하나 말고는 상태를 갖지 않는다. 자료원 설정의 `scope.extra`에서 `repo`(`소유자/이름`)와 `ref`를 읽는다.

### `list_page(session, config, cursor) -> ListPage`

`cursor`는 항상 `None`으로 불린다(한 페이지). 다음 요청을 순서대로 `session.send`로 보낸다.

| 순서 | 요청 URL | `Accept` | 실패 |
| --- | --- | --- | --- |
| 1 | `https://api.github.com/repos/{owner}/{repo}` | `application/vnd.github+json` | 세션의 `SourceFailure`·`RunStopped`를 그대로 올린다 |
| 2 | `https://api.github.com/repos/{owner}/{repo}/commits/{quote(ref, safe="")}` | 같음 | 같음 |
| 3 | `https://api.github.com/repos/{owner}/{repo}/git/trees/{tree_sha}?recursive=1` | 같음 | 같음 |

- 응답 형식이 [data-model.md 2절](../data-model.md#2-github-응답에서-읽는-값-어댑터-내부)과 다르면 `InvalidResponse`.
- 2번(커밋 확정) 요청이 `SourceFailure`(HTTP 404 또는 422)로 끝나면 `SourceFailure(NOT_FOUND, 원래 상태 코드)`로 바꿔 올린다. 1번의 404는 이미 `NOT_FOUND`다.
  그 밖 실패(409 포함)는 그대로 올린다(research R-07).
- 돌려주는 값: `ListPage(items=경로순 정렬한 일반 파일 항목, next_cursor=None, complete=not truncated)`.
- 부수 기록: 2번이 성공하면 `last_snapshot = ListSnapshot(commit_sha, visibility 원값, truncated)`을 갱신한다(3번 전이면 `truncated=None`).
  목록 조회를 시작할 때 `None`으로 비운다. 측정 명령만 읽는다(research R-14). 다른 메서드의 동작은 이 값에 기대지 않는다.
- 범위(포함·제외 패턴) 적용과 중복 제거는 하지 않는다. `list_all`이 한다.

### `fetch_content(session, config, item) -> SourceContent`

| 요청 URL | `Accept` |
| --- | --- |
| `https://api.github.com/repos/{owner}/{repo}/git/blobs/{item.change_key}` | `application/vnd.github.raw+json` |

1. 본문 바이트의 git blob SHA를 계산해 `item.change_key`와 비교한다. 다르면 `InvalidResponse`.
2. UTF-8 엄격 디코드. 실패하면 `InvalidResponse`.
3. `SourceContent(item.source_id, body, 확장자별 형식, item.version, item.location, None)`을 돌려준다.

목록 크기가 상한을 넘는 항목은 ING-001 `fetch_contents`가 이 메서드를 부르지 않고 `SIZE_EXCEEDED`로 기록한다.

### `classify(response) -> ResponseClass`

| 조건 | 결과 |
| --- | --- |
| `status in {403, 429}` 이고 `x-ratelimit-remaining == "0"` | `ResponseClass(TRANSIENT, RATE_LIMITED)` |
| `status in {403, 429}` 이고 `retry-after` 헤더 있음 | `ResponseClass(TRANSIENT, RATE_LIMITED)` |
| `status == 403` | `ResponseClass(PERMANENT, ACCESS_DENIED)` |
| 그 밖 | `default_classify(response)` |

### `rate_limit_hint(response) -> RateLimitHint | None`

| 헤더 | `remaining` | `retry_at` |
| --- | --- | --- |
| `retry-after` 있음(2차 한도 포함) | 0 (`x-ratelimit-remaining` 무시) | `retry-after` 시각. `x-ratelimit-remaining == 0`이면 `x-ratelimit-reset`과 비교해 늦은 시각 |
| `retry-after` 없음, `x-ratelimit-remaining == 0` | 0 | `x-ratelimit-reset`(유닉스 초, UTC). 없으면 `None` |
| `retry-after` 없음, `x-ratelimit-remaining > 0` | 그 값 | `None` |
| 셋 다 없음 | — | 힌트 `None` |

ING-001 요청 관문은 `remaining == 0`이고 `retry_at`이 있을 때만 다음 요청을 늦춘다. 위 정규화로 2차 한도의 대기 시각이 같은 자료의 재시도뿐 아니라
다음 자료의 요청에도 적용된다(research R-07).

### 보장

- 원본 쓰기 요청 0건. 모든 요청은 `GET`이고 허용 호스트 `api.github.com`으로 간다(ING-001 세션이 강제).
- 결과와 예외에 토큰·요청 헤더·응답 본문을 넣지 않는다.
- 같은 응답이면 같은 `ListPage`(항목, 순서, 값)를 돌려준다.

## `HttpsTransport` (`adapters/http.py`)

`SourceTransport`를 구현한다. 생성 인자는 [data-model.md 5절](../data-model.md#5-실제-전송-httpstransport-adapterhttppy).

| 상황 | 동작 |
| --- | --- |
| 2xx·4xx·5xx 응답 | `SourceResponse(status, headers, body[:max_bytes], truncated)` |
| 3xx 응답 | 따라가지 않고 그대로 돌려준다. 세션이 허용 호스트를 확인해 다시 요청한다 |
| 본문이 `max_bytes`를 넘음 | `max_bytes`까지만 담고 `truncated=True` |
| 시간 초과(`TimeoutError`, `socket.timeout`) | `TransportError("timeout")` |
| 연결 실패·이름 해석 실패·TLS 오류(`URLError`, `OSError`) | `TransportError("connection")` |
| 요청 호스트가 `auth_hosts`에 있음 | `Authorization: Bearer <토큰>`을 붙인다 |
| 그 밖 호스트 | 인증 헤더를 붙이지 않는다 |

항상 붙이는 헤더: `User-Agent`, `X-GitHub-Api-Version: 2022-11-28`. 요청의 `headers`가 같은 이름을 주면 요청 쪽이 이긴다(`Authorization` 제외).
전송은 로그를 남기지 않고, 예외 메시지는 `"timeout"`·`"connection"`뿐이다.
