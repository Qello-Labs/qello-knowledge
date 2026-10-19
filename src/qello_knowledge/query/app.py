"""질의응답 요청 처리. 로컬 서버와 Workers 겉껍질이 같은 함수를 부른다(research R-11)."""

from __future__ import annotations

from collections.abc import Callable

from qello_knowledge.config.check import CheckReport

Response = tuple[int, str]


def handle(method: str, path: str, report: Callable[[], CheckReport]) -> Response:
    """`GET /healthz`만 처리한다. 실제 질의응답은 후속 명세(QK-BOT-001 등)가 채운다."""
    if path != "/healthz":
        return 404, '{"error": "not found"}'
    if method != "GET":
        return 405, '{"error": "method not allowed"}'
    result = report()
    return (200 if result.ok else 503), result.to_json()
