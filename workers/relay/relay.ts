// 중계 판단. Workers 런타임 API 없이 표준 Web API만 쓴다(ADR-024, 이전 `discord/relay.py`와 같은 계약).

export const MAX_BODY_BYTES = 65536;
export const SIGNATURE_HEADERS = ["X-Signature-Ed25519", "X-Signature-Timestamp"] as const;

export type HeaderMap = Record<string, string>;

export type RelayRequest = { path: string; body: Uint8Array; headers: HeaderMap };

export type RelayResult = {
  body: Record<string, unknown>;
  logKind: "relayed" | "relay_failed";
  runId: string | null;
  log(elapsedMs: number): { kind: string; elapsed_ms: number };
};

export function signatureHeaders(headers: HeaderMap): HeaderMap {
  const lowered = new Map(Object.entries(headers).map(([k, v]) => [k.toLowerCase(), v]));
  return Object.fromEntries(SIGNATURE_HEADERS.map((name) => [name, lowered.get(name.toLowerCase()) ?? ""]));
}

export function precheck(body: Uint8Array, headers: HeaderMap, now: number): number | null {
  if (body.byteLength > MAX_BODY_BYTES) return 413;
  const values = signatureHeaders(headers);
  const timestamp = values["X-Signature-Timestamp"];
  if (!/^[0-9]{1,20}$/.test(timestamp)) return 401;
  if (!/^[0-9a-fA-F]{128}$/.test(values["X-Signature-Ed25519"])) return 401;
  if (!Number.isFinite(now) || Math.abs(now - Number(timestamp)) > 300) return 401;
  return null;
}

function parseObject(bytes: Uint8Array): Record<string, unknown> | null {
  try {
    const payload = JSON.parse(new TextDecoder("utf-8", { fatal: true }).decode(bytes));
    return payload !== null && typeof payload === "object" && !Array.isArray(payload) ? payload : null;
  } catch {
    return null;
  }
}

function isPing(body: Uint8Array): boolean {
  return parseObject(body)?.type === 1;
}

export function fallback() {
  return {
    type: 4,
    data: {
      content: "지금은 답할 수 없습니다. 잠시 후 다시 질문해 주세요.",
      flags: 64,
      allowed_mentions: { parse: [] },
    },
  };
}

function result(body: Record<string, unknown>, logKind: RelayResult["logKind"], runId: string | null = null): RelayResult {
  return { body, logKind, runId, log: (elapsedMs) => ({ kind: logKind, elapsed_ms: elapsedMs }) };
}

export function relayPlan(body: Uint8Array, headers: HeaderMap): RelayRequest[] {
  return isPing(body) ? [] : [{ path: "/discord/interactions", body, headers: signatureHeaders(headers) }];
}

export function relayResponse(original: Uint8Array, status: number | null, body: Uint8Array, headers: HeaderMap): RelayResult {
  if (isPing(original)) return result({ type: 1 }, "relayed");
  if (status === 200) {
    const payload = parseObject(body);
    if (payload && (payload.type === 1 || payload.type === 4 || payload.type === 5)) {
      const run = Object.entries(headers).find(([k]) => k.toLowerCase() === "x-qk-run")?.[1] ?? null;
      return result(payload, "relayed", payload.type === 5 ? run : null);
    }
  }
  return result(fallback(), "relay_failed");
}

export function startRequest(relayed: RelayResult, headers: HeaderMap): RelayRequest | null {
  if (relayed.runId === null) return null;
  return {
    path: "/discord/interactions/start",
    body: new TextEncoder().encode(JSON.stringify({ run_id: relayed.runId })),
    headers: signatureHeaders(headers),
  };
}
