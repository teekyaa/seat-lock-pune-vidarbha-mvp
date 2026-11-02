import { NextRequest } from "next/server";

/** Trust a client IP header only when an operator configures a sanitizing ingress. */
export function trustedClientIp(request: NextRequest): string {
  const name = process.env.SEATLOCK_CLIENT_IP_HEADER;
  return name ? (request.headers.get(name) ?? "").split(",")[0].trim() : "";
}

/** The browser proxy authenticates with cookies, so writes must originate on this site. */
export function hasSameOrigin(request: NextRequest): boolean {
  const origin = request.headers.get("origin");
  const host = request.headers.get("host");
  if (!origin || !host) return false;
  try {
    const url = new URL(origin);
    const forwarded = request.headers.get("x-forwarded-proto");
    const protocol = forwarded ? `${forwarded.split(",")[0].trim()}:` : request.nextUrl.protocol;
    return (protocol === "http:" || protocol === "https:") && url.protocol === protocol &&
      url.origin === origin && url.host.toLowerCase() === host.toLowerCase();
  } catch {
    return false;
  }
}

export async function readLimitedBody(request: NextRequest, limit = 65536): Promise<string> {
  const declared = request.headers.get("content-length");
  if (declared && (!/^\d+$/.test(declared) || Number(declared) > limit)) throw new Error("body_too_large");
  if (!request.body) return "";
  const reader = request.body.getReader();
  const decoder = new TextDecoder();
  let bytes = 0;
  let text = "";
  while (true) {
    const { value, done } = await reader.read();
    if (done) break;
    bytes += value.byteLength;
    if (bytes > limit) {
      await reader.cancel();
      throw new Error("body_too_large");
    }
    text += decoder.decode(value, { stream: true });
  }
  return text + decoder.decode();
}
