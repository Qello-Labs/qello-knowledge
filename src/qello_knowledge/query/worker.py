"""Cloudflare Python Workers 겉껍질. `handle`을 부르기만 한다.

`workers` 모듈은 Workers 런타임에만 있어 테스트에서 이 파일을 가져오지 않는다.
배포 설정(`wrangler.toml`, `pywrangler`)과 이 파일의 실제 실행 검증은 QK-BOT-001에서 한다.
Workers에는 `.env`가 없으므로 바인딩 환경값(`self.env`)을 설정 원천으로 넘긴다.
"""

from __future__ import annotations

from urllib.parse import urlsplit

from workers import Response, WorkerEntrypoint  # type: ignore[import-not-found]

from qello_knowledge.config.check import build_report
from qello_knowledge.config.loader import load
from qello_knowledge.config.registry import Entrypoint, specs_for
from qello_knowledge.query.app import handle


class Default(WorkerEntrypoint):
    async def fetch(self, request):
        environ = {}
        for spec in specs_for(Entrypoint.QUERY):
            value = getattr(self.env, spec.name, None)
            if value is not None:
                environ[spec.name] = str(value)

        def report():
            return build_report(load(Entrypoint.QUERY, environ=environ, env_file=None))

        status, body = handle(request.method, urlsplit(request.url).path, report)
        return Response(body, status=status, headers={"Content-Type": "application/json; charset=utf-8"})
