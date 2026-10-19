"""저장된 가상 응답만 재생한다. 준비되지 않은 요청은 시험 실패다."""

from __future__ import annotations

import json
from collections import deque
from pathlib import Path

from qello_knowledge.domain.source import SourceRequest, SourceResponse, TransportError


class ReplayTransport:
    def __init__(self, exchanges: list[dict]):
        self.requests: list[SourceRequest] = []
        self._responses: dict[tuple[str, str], deque] = {}
        for exchange in exchanges:
            key = (exchange["method"], exchange["url"])
            self._responses.setdefault(key, deque()).extend(exchange["responses"])

    @classmethod
    def from_file(cls, path: Path) -> ReplayTransport:
        data = json.loads(path.read_text(encoding="utf-8"))
        meta = data.get("_meta")
        if not isinstance(meta, dict) or not {"source_api", "saved_at", "redactions"} <= meta.keys():
            raise ValueError("응답 샘플 메타데이터가 필요하다")
        return cls(data["body"]["exchanges"])

    def send(self, request: SourceRequest) -> SourceResponse:
        self.requests.append(request)
        responses = self._responses.get((request.method, request.url))
        if not responses:
            raise AssertionError("준비되지 않았거나 소진된 재생 요청")
        response = responses.popleft()
        if "error" in response:
            raise TransportError(response["error"])
        body = response["body"]
        raw = (body if isinstance(body, str) else json.dumps(body, ensure_ascii=False)).encode("utf-8")
        truncated = request.max_bytes is not None and len(raw) > request.max_bytes
        if truncated:
            raw = raw[: request.max_bytes]
        return SourceResponse(response["status"], response["headers"], raw, truncated)
