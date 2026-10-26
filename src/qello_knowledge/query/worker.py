"""Cloudflare Python Workers 중계 겉껍질.

`workers` 모듈은 Workers 런타임에만 있어 테스트에서 이 파일을 가져오지 않는다.
배포 설정(`wrangler.toml`, `pywrangler`)과 이 파일의 실제 실행 검증은 사람 단계 H01에서 한다.
Workers에는 `.env`가 없으므로 바인딩 환경값(`self.env`)을 설정 원천으로 넘긴다.
FFI와 VPC fetch·waitUntil의 실제 API 꼴은 H01에서 확인한다.
"""

from __future__ import annotations

import asyncio
import json
from time import monotonic, time
from urllib.parse import urlsplit

from js import Object, Uint8Array, crypto  # type: ignore[import-not-found]
from pyodide.ffi import to_js  # type: ignore[import-not-found]
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
                "http://127.0.0.1:8787" + plan.path,
                _js({"method": "POST", "headers": plan.headers, "body": _bytes(plan.body)}),
            ),
            timeout,
        )

    async def _start(self, plan, timeout):
        started = monotonic()
        ok = False
        try:
            response = await self._fetch_service(plan, timeout)
            ok = response.status == 204
        except Exception:
            ok = False
        if not ok:
            print(json.dumps({"kind": "start_failed", "elapsed_ms": int((monotonic() - started) * 1000)}))

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
        body = bytes(Uint8Array.new(await request.arrayBuffer()).to_py())
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
        try:

            async def relay():
                response = await self._fetch_service(plan[0], timeout)
                raw = bytes(Uint8Array.new(await response.arrayBuffer()).to_py())
                return relay_response(
                    body,
                    response.status,
                    raw,
                    {"X-QK-Run": response.headers.get("X-QK-Run")} if response.headers.has("X-QK-Run") else {},
                )

            result = await asyncio.wait_for(relay(), timeout)
        except Exception:
            result = relay_response(body, None, b"", {})
        print(json.dumps(result.log(int((monotonic() - started) * 1000))))
        response = _json_response(result.body)
        start = start_request(result, headers)
        if start is not None:
            self.ctx.waitUntil(self._start(start, timeout))
        return response
