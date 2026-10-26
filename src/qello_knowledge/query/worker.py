"""Cloudflare Python Workers 중계 겉껍질.

`workers` 모듈은 Workers 런타임에만 있어 테스트에서 이 파일을 가져오지 않는다.
배포 설정(`wrangler.toml`, `pywrangler`)과 이 파일의 실제 실행 검증은 사람 단계 H01에서 한다.
Workers에는 `.env`가 없으므로 바인딩 환경값(`self.env`)을 설정 원천으로 넘긴다.
요청 본문은 SDK의 `bytes()`를 쓴다(H01 로컬 확인, 2026-10-26).
VPC 바인딩은 SDK가 Fetcher로 감싸 `fetch(url, **kwargs)`를 받는다고 보고 그 꼴로 부른다
(SDK 소스 기준 추론, 배포 H01에서 확인).
실패 로그에는 예외 클래스 이름만 남기고 메시지·본문은 남기지 않는다.
"""

from __future__ import annotations

import asyncio
import json
from time import monotonic, time
from urllib.parse import urlsplit

from js import Object, Uint8Array, crypto  # type: ignore[import-not-found]
from pyodide.ffi import create_proxy, to_js  # type: ignore[import-not-found]
from workers import Response, WorkerEntrypoint  # type: ignore[import-not-found]

from qello_knowledge.config.check import build_report
from qello_knowledge.config.loader import load
from qello_knowledge.config.registry import Entrypoint, specs_for
from qello_knowledge.discord.relay import precheck, relay_plan, relay_response, signature_headers, start_request


def _js(value):
    return to_js(value, dict_converter=Object.fromEntries)


def _bytes(value):
    return Uint8Array.new(_js(list(value)))


def _json_response(body, status=200):
    return Response(
        json.dumps(body, ensure_ascii=False), status=status, headers={"Content-Type": "application/json; charset=utf-8"}
    )


class Default(WorkerEntrypoint):
    async def _fetch_service(self, plan, timeout):
        # URL은 VPC 바인딩의 루프백 대상이다. 공개 호스트명을 만들지 않는다(R-02).
        return await asyncio.wait_for(
            self.env.QUERY_SERVICE.fetch(
                "http://127.0.0.1:8787" + plan.path, method="POST", headers=plan.headers, body=_bytes(plan.body)
            ),
            timeout,
        )

    async def _start(self, plan, timeout):
        started = monotonic()
        error = None
        try:
            response = await self._fetch_service(plan, timeout)
            if response.status != 204:
                error = f"status_{response.status}"
        except Exception as exc:
            error = type(exc).__name__
        if error is not None:
            elapsed_ms = int((monotonic() - started) * 1000)
            print(json.dumps({"kind": "start_failed", "elapsed_ms": elapsed_ms, "error": error}))

    async def fetch(self, request):
        environ = {}
        for spec in specs_for(Entrypoint.RELAY):
            value = getattr(self.env, spec.name, None)
            if value is not None:
                environ[spec.name] = str(value)
        settings = load(Entrypoint.RELAY, environ=environ, env_file=None)
        report = build_report(settings)
        path = urlsplit(request.url).path
        if path == "/healthz":
            if request.method != "GET":
                return Response("", status=405)
            return Response(
                report.to_json(),
                status=200 if report.ok else 503,
                headers={"Content-Type": "application/json; charset=utf-8"},
            )
        if path != "/discord/interactions":
            return Response("", status=404)
        if request.method != "POST":
            return Response("", status=405)
        try:
            declared = request.headers.get("Content-Length")
            if declared is not None and int(declared) > 65536:
                return Response("", status=413)
        except (ValueError, TypeError):
            return Response("", status=400)
        body = await request.bytes()
        headers = {
            name: str(request.headers.get(name) or "") for name in ("X-Signature-Ed25519", "X-Signature-Timestamp")
        }
        rejected = precheck(body, headers, time())
        if rejected is not None:
            return Response("", status=rejected)
        if not report.ok:
            return Response("", status=503)
        signed = signature_headers(headers)
        try:
            key = await crypto.subtle.importKey(
                "raw", _bytes(bytes.fromhex(settings.get("DISCORD_PUBLIC_KEY"))), "Ed25519", False, _js(["verify"])
            )
            valid = await crypto.subtle.verify(
                "Ed25519",
                key,
                _bytes(bytes.fromhex(signed["X-Signature-Ed25519"])),
                _bytes(signed["X-Signature-Timestamp"].encode() + body),
            )
        except Exception:
            return Response("", status=401)
        if not valid:
            return Response("", status=401)
        plan = relay_plan(body, headers)
        if not plan:
            return _json_response({"type": 1})
        timeout = float(settings.get("QK_RELAY_TIMEOUT_SECONDS"))
        started = monotonic()
        error = None
        try:

            async def relay():
                response = await self._fetch_service(plan[0], timeout)
                raw = await response.bytes()
                return relay_response(
                    body,
                    response.status,
                    raw,
                    {"X-QK-Run": response.headers.get("X-QK-Run")} if response.headers.get("X-QK-Run") else {},
                )

            result = await asyncio.wait_for(relay(), timeout)
        except Exception as exc:
            error = type(exc).__name__
            result = relay_response(body, None, b"", {})
        log = result.log(int((monotonic() - started) * 1000))
        if error is not None:
            log["error"] = error
        print(json.dumps(log))
        response = _json_response(result.body)
        start = start_request(result, headers)
        if start is not None:
            # SDK의 ASGI 구현처럼 작업을 프록시로 넘기고, 끝나면 프록시를 정리한다.
            task = asyncio.ensure_future(self._start(start, timeout))
            proxy = create_proxy(task)
            task.add_done_callback(lambda _: proxy.destroy())
            self.ctx.waitUntil(proxy)
        return response
