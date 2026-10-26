// 중계 Worker 계약 시험. Python `tests/unit/discord/test_bot_relay.py`의 기대값을 옮기고(ADR-024),
// Worker 진입점을 가짜 VPC 바인딩·waitUntil로 끝까지 돌린다. npm 의존성 없이 `node --test workers/relay/`로 돈다.
import assert from "node:assert/strict";
import { test } from "node:test";

import worker from "./index.ts";
import { fallback, MAX_BODY_BYTES, precheck, relayPlan, relayResponse, startRequest } from "./relay.ts";

const BOT_HEADERS = { "X-Signature-Ed25519": "a".repeat(128), "X-Signature-Timestamp": "1000" };
const enc = (text: string) => new TextEncoder().encode(text);

test("precheck와 PING", () => {
  assert.equal(precheck(new Uint8Array(65537), BOT_HEADERS, 1000), 413);
  assert.equal(precheck(enc("{}"), {}, 1000), 401);
  assert.equal(precheck(enc("{}"), BOT_HEADERS, 1300), null);
  assert.equal(precheck(enc("{}"), BOT_HEADERS, 1300.01), 401);
  assert.equal(precheck(enc("{}"), BOT_HEADERS, 699.99), 401);
  assert.equal(precheck(enc("{}"), { ...BOT_HEADERS, "X-Signature-Timestamp": "NaN" }, 1000), 401);
  assert.equal(precheck(enc("{}"), { ...BOT_HEADERS, "X-Signature-Ed25519": "z".repeat(128) }, 1000), 401);
  assert.equal(precheck(enc("{}"), BOT_HEADERS, Number.NaN), 401);
  assert.deepEqual(relayPlan(enc('{"type":1}'), BOT_HEADERS), []);
  assert.equal(MAX_BODY_BYTES, 65536);
});

for (const status of [null, 500, 401]) {
  test(`질의 서비스 실패(${status})는 대체 안내`, () => {
    const result = relayResponse(enc('{"type":2}'), status, new Uint8Array(), {});
    assert.deepEqual(result.body, fallback());
    assert.equal(result.logKind, "relay_failed");
    assert.equal(result.runId, null);
    assert.deepEqual(fallback(), {
      type: 4,
      data: {
        content: "지금은 답할 수 없습니다. 잠시 후 다시 질문해 주세요.",
        flags: 64,
        allowed_mentions: { parse: [] },
      },
    });
    assert.deepEqual(relayResponse(enc('{"type":1}'), null, new Uint8Array(), {}).body, { type: 1 });
  });
}

test("본문 그대로 중계, 시작 확인, 기록 허용 목록", () => {
  const body = enc('{"type":2}');
  const plan = relayPlan(body, BOT_HEADERS);
  assert.equal(plan.length, 1);
  assert.deepEqual(plan[0].body, body);
  assert.deepEqual(plan[0].headers, BOT_HEADERS);
  const result = relayResponse(body, 200, enc('{"type":5}'), { "X-QK-Run": "run" });
  assert.deepEqual(result.body, { type: 5 });
  assert.equal(result.logKind, "relayed");
  const start = startRequest(result, BOT_HEADERS);
  assert.ok(start);
  assert.equal(start.path, "/discord/interactions/start");
  assert.deepEqual(JSON.parse(new TextDecoder().decode(start.body)), { run_id: "run" });
  assert.deepEqual(start.headers, BOT_HEADERS);
  assert.equal(startRequest(relayResponse(body, 200, enc('{"type":4}'), {}), BOT_HEADERS), null);
  assert.equal(relayResponse(body, 200, enc('{"type":4}'), { "x-qk-run": "run" }).runId, null);
  assert.deepEqual(Object.keys(result.log(12)).sort(), ["elapsed_ms", "kind"]);
  assert.deepEqual(relayResponse(body, 200, enc("not json"), {}).body, fallback());
  assert.deepEqual(relayResponse(body, 200, enc('{"type":7}'), {}).body, fallback());
});

// --- Worker 진입점: 실제 Ed25519 서명과 가짜 바인딩 ---

type Call = { url: string; method: string; headers: Record<string, string>; body: Uint8Array };

async function keyPair() {
  const pair = (await crypto.subtle.generateKey({ name: "Ed25519" }, true, ["sign", "verify"])) as CryptoKeyPair;
  const raw = new Uint8Array(await crypto.subtle.exportKey("raw", pair.publicKey));
  const hex = Array.from(raw, (b) => b.toString(16).padStart(2, "0")).join("");
  return { privateKey: pair.privateKey, publicHex: hex };
}

async function signed(privateKey: CryptoKey, payload: unknown, timestamp = String(Math.floor(Date.now() / 1000))) {
  const body = JSON.stringify(payload);
  const sig = new Uint8Array(await crypto.subtle.sign("Ed25519", privateKey, enc(timestamp + body)));
  const hex = Array.from(sig, (b) => b.toString(16).padStart(2, "0")).join("");
  return new Request("https://relay.example/discord/interactions", {
    method: "POST",
    headers: { "X-Signature-Ed25519": hex, "X-Signature-Timestamp": timestamp, "Content-Type": "application/json" },
    body,
  });
}

function fakeEnv(publicHex: string, reply: (call: Call) => Response | Promise<Response>, extra: Record<string, string> = {}) {
  const calls: Call[] = [];
  const env = {
    DISCORD_PUBLIC_KEY: publicHex,
    ...extra,
    QUERY_SERVICE: {
      async fetch(url: string, init: { method: string; headers: Record<string, string>; body: Uint8Array }) {
        const call = { url, method: init.method, headers: init.headers, body: new Uint8Array(init.body) };
        calls.push(call);
        return reply(call);
      },
    },
  };
  return { env, calls };
}

function fakeCtx() {
  const pending: Promise<unknown>[] = [];
  return { ctx: { waitUntil: (p: Promise<unknown>) => void pending.push(p) }, pending };
}

async function captureLogs<T>(run: () => Promise<T>): Promise<{ value: T; logs: unknown[] }> {
  const logs: unknown[] = [];
  const original = console.log;
  console.log = (line: unknown) => void logs.push(JSON.parse(String(line)));
  try {
    return { value: await run(), logs };
  } finally {
    console.log = original;
  }
}

test("healthz는 설정 이름·상태만 보인다", async () => {
  const { publicHex } = await keyPair();
  const ok = await worker.fetch(new Request("https://relay.example/healthz"), fakeEnv(publicHex, () => new Response()).env, fakeCtx().ctx);
  assert.equal(ok.status, 200);
  assert.deepEqual(await ok.json(), {
    entrypoint: "relay",
    ok: true,
    items: [
      { name: "DISCORD_PUBLIC_KEY", status: "OK" },
      { name: "QK_RELAY_TIMEOUT_SECONDS", status: "OK" },
    ],
    checks: [],
    warnings: [],
  });
  const missing = await worker.fetch(new Request("https://relay.example/healthz"), fakeEnv("", () => new Response()).env, fakeCtx().ctx);
  assert.equal(missing.status, 503);
  const body = await missing.json();
  assert.equal(body.items[0].status, "MISSING");
  const bad = fakeEnv(publicHex, () => new Response(), { QK_RELAY_TIMEOUT_SECONDS: "9" }).env;
  const invalid = await worker.fetch(new Request("https://relay.example/healthz"), bad, fakeCtx().ctx);
  assert.equal(invalid.status, 503);
  assert.equal((await invalid.json()).items[1].status, "INVALID");
  assert.equal((await worker.fetch(new Request("https://relay.example/healthz", { method: "POST" }), bad, fakeCtx().ctx)).status, 405);
});

test("경로·메서드·크기·서명 거부", async () => {
  const { privateKey, publicHex } = await keyPair();
  const { env, calls } = fakeEnv(publicHex, () => new Response());
  const { ctx } = fakeCtx();
  assert.equal((await worker.fetch(new Request("https://relay.example/other"), env, ctx)).status, 404);
  assert.equal((await worker.fetch(new Request("https://relay.example/discord/interactions"), env, ctx)).status, 405);
  const big = new Request("https://relay.example/discord/interactions", {
    method: "POST",
    headers: { "Content-Length": "70000" },
    body: "x",
  });
  assert.equal((await worker.fetch(big, env, ctx)).status, 413);
  const unsigned = new Request("https://relay.example/discord/interactions", { method: "POST", body: '{"type":1}' });
  assert.equal((await worker.fetch(unsigned, env, ctx)).status, 401);
  const good = await signed(privateKey, { type: 1 });
  const tampered = new Request(good.url, {
    method: "POST",
    headers: good.headers,
    body: '{"type":1, "x":1}',
  });
  assert.equal((await worker.fetch(tampered, env, ctx)).status, 401);
  const old = await signed(privateKey, { type: 1 }, String(Math.floor(Date.now() / 1000) - 600));
  assert.equal((await worker.fetch(old, env, ctx)).status, 401);
  const noKey = fakeEnv("", () => new Response()).env;
  assert.equal((await worker.fetch(await signed(privateKey, { type: 1 }), noKey, ctx)).status, 503);
  assert.equal(calls.length, 0);
});

test("서명된 PING은 질의 서비스를 부르지 않는다", async () => {
  const { privateKey, publicHex } = await keyPair();
  const { env, calls } = fakeEnv(publicHex, () => new Response());
  const response = await worker.fetch(await signed(privateKey, { type: 1 }), env, fakeCtx().ctx);
  assert.equal(response.status, 200);
  assert.deepEqual(await response.json(), { type: 1 });
  assert.equal(calls.length, 0);
});

test("명령은 본문·서명 헤더 그대로 중계하고, 지연 응답이면 waitUntil로 시작 확인을 보낸다", async () => {
  const { privateKey, publicHex } = await keyPair();
  const { env, calls } = fakeEnv(publicHex, (call) =>
    call.url.endsWith("/start")
      ? new Response(null, { status: 204 })
      : new Response(JSON.stringify({ type: 5, data: { flags: 64 } }), { headers: { "X-QK-Run": "q-1" } }),
  );
  const { ctx, pending } = fakeCtx();
  const request = await signed(privateKey, { type: 2, data: { name: "ask" } });
  const sent = new Uint8Array(await request.clone().arrayBuffer());
  const { value: response, logs } = await captureLogs(async () => {
    const r = await worker.fetch(request, env, ctx);
    await Promise.all(pending);
    return r;
  });
  assert.equal(response.status, 200);
  assert.deepEqual(await response.json(), { type: 5, data: { flags: 64 } });
  assert.equal(calls.length, 2);
  assert.equal(calls[0].url, "http://127.0.0.1:8787/discord/interactions");
  assert.equal(calls[0].method, "POST");
  assert.deepEqual(calls[0].body, sent);
  assert.deepEqual(Object.keys(calls[0].headers).sort(), ["X-Signature-Ed25519", "X-Signature-Timestamp"]);
  assert.equal(calls[1].url, "http://127.0.0.1:8787/discord/interactions/start");
  assert.deepEqual(JSON.parse(new TextDecoder().decode(calls[1].body)), { run_id: "q-1" });
  assert.deepEqual(calls[1].headers, calls[0].headers);
  assert.equal(logs.length, 1);
  assert.deepEqual(Object.keys(logs[0] as object).sort(), ["elapsed_ms", "kind"]);
  assert.equal((logs[0] as { kind: string }).kind, "relayed");
});

test("즉시 안내(type 4)는 시작 확인을 보내지 않는다", async () => {
  const { privateKey, publicHex } = await keyPair();
  const notice = { type: 4, data: { content: "허용되지 않은 채널입니다.", flags: 64 } };
  const { env, calls } = fakeEnv(publicHex, () => new Response(JSON.stringify(notice), { headers: { "X-QK-Run": "q-2" } }));
  const { ctx, pending } = fakeCtx();
  const request = await signed(privateKey, { type: 2 });
  const { value: response } = await captureLogs(() => worker.fetch(request, env, ctx));
  assert.deepEqual(await response.json(), notice);
  assert.equal(pending.length, 0);
  assert.equal(calls.length, 1);
});

test("질의 서비스 실패·시간 초과는 대체 안내와 예외 이름만 기록한다", async () => {
  const { privateKey, publicHex } = await keyPair();
  const failing = fakeEnv(publicHex, () => {
    throw new TypeError("secret detail that must not be logged");
  });
  const { value: failed, logs } = await captureLogs(async () =>
    worker.fetch(await signed(privateKey, { type: 2 }), failing.env, fakeCtx().ctx),
  );
  assert.deepEqual(await failed.json(), fallback());
  assert.deepEqual(logs, [{ kind: "relay_failed", elapsed_ms: (logs[0] as { elapsed_ms: number }).elapsed_ms, error: "TypeError" }]);
  assert.ok(!JSON.stringify(logs).includes("secret detail"));

  const slow = fakeEnv(publicHex, () => new Promise<Response>(() => {}), { QK_RELAY_TIMEOUT_SECONDS: "0.5" });
  const started = Date.now();
  const { value: timedOut, logs: slowLogs } = await captureLogs(async () =>
    worker.fetch(await signed(privateKey, { type: 2 }), slow.env, fakeCtx().ctx),
  );
  assert.ok(Date.now() - started < 1500);
  assert.deepEqual(await timedOut.json(), fallback());
  assert.equal((slowLogs[0] as { error: string }).error, "TimeoutError");
});

test("응답 헤더 대기와 본문 읽기를 합친 시간이 중계 제한 시간 안이다", async () => {
  const { privateKey, publicHex } = await keyPair();
  // 헤더는 늦게 오고 본문은 끝나지 않는다. 두 단계에 제한 시간이 따로 걸리면 900 + 1000 = 1.9초 아래로 내려갈 수 없다.
  const slowBody = fakeEnv(
    publicHex,
    () =>
      new Promise<Response>((resolve) =>
        setTimeout(() => resolve(new Response(new ReadableStream({ start() {} }))), 900),
      ),
    { QK_RELAY_TIMEOUT_SECONDS: "1.0" },
  );
  const request = await signed(privateKey, { type: 2 });
  const started = Date.now();
  const { value: response, logs } = await captureLogs(() => worker.fetch(request, slowBody.env, fakeCtx().ctx));
  const elapsed = Date.now() - started;
  // 정상은 약 1.0초다. 느린 러너의 여유를 두되, 회귀(1.9초 이상)와 200 ms 넘게 떨어뜨린다.
  assert.ok(elapsed < 1700, `elapsed ${elapsed} ms`);
  assert.deepEqual(await response.json(), fallback());
  assert.equal((logs[0] as { error: string }).error, "TimeoutError");
});

test("숫자가 아닌 Content-Length는 400", async () => {
  const { publicHex } = await keyPair();
  const { env, calls } = fakeEnv(publicHex, () => new Response());
  const request = new Request("https://relay.example/discord/interactions", {
    method: "POST",
    headers: { "Content-Length": "-5" },
    body: "{}",
  });
  assert.equal((await worker.fetch(request, env, fakeCtx().ctx)).status, 400);
  assert.equal(calls.length, 0);
});

test("시작 확인 실패는 상태나 예외 이름만 기록한다", async () => {
  const { privateKey, publicHex } = await keyPair();
  const { env } = fakeEnv(publicHex, (call) =>
    call.url.endsWith("/start")
      ? new Response(null, { status: 409 })
      : new Response(JSON.stringify({ type: 5 }), { headers: { "X-QK-Run": "q-3" } }),
  );
  const { ctx, pending } = fakeCtx();
  const { logs } = await captureLogs(async () => {
    await worker.fetch(await signed(privateKey, { type: 2 }), env, ctx);
    await Promise.all(pending);
  });
  const start = logs.find((line) => (line as { kind: string }).kind === "start_failed") as Record<string, unknown>;
  assert.deepEqual(Object.keys(start).sort(), ["elapsed_ms", "error", "kind"]);
  assert.equal(start.error, "status_409");
});
