// Cloudflare Worker 중계 진입점(ADR-022·ADR-024). 서명 검사와 질의 서비스 중계만 하고 도메인 판단은 질의 서비스가 한다.
// 설정은 `DISCORD_PUBLIC_KEY`(비밀값), `QK_RELAY_TIMEOUT_SECONDS`, VPC 바인딩 `QUERY_SERVICE`뿐이다.
// 기록에는 결과 종류·경과 시간·예외 이름(또는 상태)만 남기고 본문·헤더·메시지는 남기지 않는다.

import { MAX_BODY_BYTES, precheck, relayPlan, relayResponse, type RelayRequest, startRequest } from "./relay.ts";

// VPC 바인딩의 루프백 대상이다. 공개 호스트명을 만들지 않는다(research R-02).
const SERVICE_ORIGIN = "http://127.0.0.1:8787";
const DEFAULT_TIMEOUT_SECONDS = "2.5";

type Fetcher = { fetch(url: string, init: { method: string; headers: Record<string, string>; body: Uint8Array; signal?: AbortSignal }): Promise<Response> };
type Env = { DISCORD_PUBLIC_KEY?: string; QK_RELAY_TIMEOUT_SECONDS?: string; QUERY_SERVICE: Fetcher };
type Context = { waitUntil(promise: Promise<unknown>): void };
type Status = "OK" | "MISSING" | "INVALID";

function settings(env: Env) {
  const key = (env.DISCORD_PUBLIC_KEY ?? "").trim();
  const timeoutRaw = (env.QK_RELAY_TIMEOUT_SECONDS ?? "").trim() || DEFAULT_TIMEOUT_SECONDS;
  const timeout = Number(timeoutRaw);
  const keyStatus: Status = !key ? "MISSING" : /^[0-9a-fA-F]{64}$/.test(key) ? "OK" : "INVALID";
  // config/registry.py RELAY_TIMEOUT와 같은 규칙: 0.5 이상 2.8 이하 초.
  const timeoutStatus: Status = /^[0-9]+(?:\.[0-9]+)?$/.test(timeoutRaw) && timeout >= 0.5 && timeout <= 2.8 ? "OK" : "INVALID";
  return {
    key,
    timeoutMs: timeout * 1000,
    ok: keyStatus === "OK" && timeoutStatus === "OK",
    report: {
      entrypoint: "relay",
      ok: keyStatus === "OK" && timeoutStatus === "OK",
      items: [
        { name: "DISCORD_PUBLIC_KEY", status: keyStatus },
        { name: "QK_RELAY_TIMEOUT_SECONDS", status: timeoutStatus },
      ],
      checks: [],
      warnings: [],
    },
  };
}

function json(body: unknown, status = 200) {
  return new Response(JSON.stringify(body), { status, headers: { "Content-Type": "application/json; charset=utf-8" } });
}

function hexBytes(hex: string): Uint8Array {
  const out = new Uint8Array(hex.length / 2);
  for (let i = 0; i < out.length; i++) out[i] = parseInt(hex.slice(i * 2, i * 2 + 2), 16);
  return out;
}

// isolate 안에서 같은 공개 키를 다시 가져오지 않는다.
const keys = new Map<string, Promise<CryptoKey>>();

function publicKey(hex: string): Promise<CryptoKey> {
  let key = keys.get(hex);
  if (!key) {
    key = crypto.subtle.importKey("raw", hexBytes(hex), { name: "Ed25519" }, false, ["verify"]);
    keys.set(hex, key);
  }
  return key;
}

async function verify(hexKey: string, headers: Record<string, string>, body: Uint8Array): Promise<boolean> {
  try {
    const timestamp = new TextEncoder().encode(headers["X-Signature-Timestamp"]);
    const message = new Uint8Array(timestamp.byteLength + body.byteLength);
    message.set(timestamp);
    message.set(body, timestamp.byteLength);
    return await crypto.subtle.verify("Ed25519", await publicKey(hexKey), hexBytes(headers["X-Signature-Ed25519"]), message);
  } catch {
    return false;
  }
}

function errorName(error: unknown): string {
  return error instanceof Error ? error.name : typeof error;
}

function callService(env: Env, plan: RelayRequest, timeoutMs: number): Promise<Response> {
  return env.QUERY_SERVICE.fetch(SERVICE_ORIGIN + plan.path, {
    method: "POST",
    headers: plan.headers,
    body: plan.body,
    signal: AbortSignal.timeout(timeoutMs),
  });
}

function withTimeout<T>(promise: Promise<T>, timeoutMs: number): Promise<T> {
  // 바인딩이 signal을 무시해도 중계는 제한 시간 안에 끝낸다.
  let timer: ReturnType<typeof setTimeout> | undefined;
  const expired = new Promise<T>((_, reject) => {
    timer = setTimeout(() => reject(new DOMException("relay timed out", "TimeoutError")), timeoutMs);
  });
  return Promise.race([promise, expired]).finally(() => clearTimeout(timer));
}

async function start(env: Env, plan: RelayRequest, timeoutMs: number): Promise<void> {
  const started = Date.now();
  let error: string | null = null;
  try {
    const response = await withTimeout(callService(env, plan, timeoutMs), timeoutMs);
    if (response.status !== 204) error = `status_${response.status}`;
  } catch (caught) {
    error = errorName(caught);
  }
  if (error !== null) console.log(JSON.stringify({ kind: "start_failed", elapsed_ms: Date.now() - started, error }));
}

export default {
  async fetch(request: Request, env: Env, ctx: Context): Promise<Response> {
    const config = settings(env);
    const path = new URL(request.url).pathname;
    if (path === "/healthz") {
      if (request.method !== "GET") return new Response("", { status: 405 });
      return json(config.report, config.ok ? 200 : 503);
    }
    if (path !== "/discord/interactions") return new Response("", { status: 404 });
    if (request.method !== "POST") return new Response("", { status: 405 });
    const declared = request.headers.get("Content-Length");
    if (declared !== null) {
      if (!/^[0-9]+$/.test(declared)) return new Response("", { status: 400 });
      if (Number(declared) > MAX_BODY_BYTES) return new Response("", { status: 413 });
    }
    const body = new Uint8Array(await request.arrayBuffer());
    const headers = {
      "X-Signature-Ed25519": request.headers.get("X-Signature-Ed25519") ?? "",
      "X-Signature-Timestamp": request.headers.get("X-Signature-Timestamp") ?? "",
    };
    const rejected = precheck(body, headers, Date.now() / 1000);
    if (rejected !== null) return new Response("", { status: rejected });
    if (!config.ok) return new Response("", { status: 503 });
    if (!(await verify(config.key, headers, body))) return new Response("", { status: 401 });
    const plan = relayPlan(body, headers);
    if (plan.length === 0) return json({ type: 1 });

    const started = Date.now();
    let error: string | null = null;
    let result;
    try {
      // 응답 헤더 대기와 본문 읽기를 합쳐 한 번의 제한 시간으로 끝낸다(Discord 3초 마감).
      const relayed = async () => {
        const response = await callService(env, plan[0], config.timeoutMs);
        const raw = new Uint8Array(await response.arrayBuffer());
        const run = response.headers.get("X-QK-Run");
        return relayResponse(body, response.status, raw, run ? { "X-QK-Run": run } : {});
      };
      result = await withTimeout(relayed(), config.timeoutMs);
    } catch (caught) {
      error = errorName(caught);
      result = relayResponse(body, null, new Uint8Array(), {});
    }
    const log: Record<string, unknown> = result.log(Date.now() - started);
    if (error !== null) log.error = error;
    console.log(JSON.stringify(log));
    const next = startRequest(result, headers);
    if (next !== null) ctx.waitUntil(start(env, next, config.timeoutMs));
    return json(result.body);
  },
};
