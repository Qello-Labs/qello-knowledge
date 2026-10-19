# 외부 API 응답 샘플

외부 API를 쓰는 기능의 기본 테스트는 여기 저장한 응답으로 돈다(QK-FND-001 FR-017, C-12).
실제 API를 부르는 테스트는 `@pytest.mark.external`을 붙이고 `uv run pytest -m external`로만 실행한다.

- 경로: `tests/fixtures/responses/<api>/<이름>.json`
- 형식:

  ```json
  {
    "_meta": {
      "source_api": "github.rest.repos.get-content",
      "saved_at": "2026-10-19",
      "redactions": ["token", "owner.id"]
    },
    "body": {}
  }
  ```

- 토큰, 계정 식별자, 내부 주소는 저장하기 전에 지우고 지운 필드를 `_meta.redactions`에 적는다.
- 샘플도 `scripts/preflight.py` 검사 대상이다. 오탐이면 `scripts/preflight_allowlist.txt`에 사유와 함께 올린다.
