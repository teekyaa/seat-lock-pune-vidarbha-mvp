import { cookies } from "next/headers";
import { NextRequest, NextResponse } from "next/server";
import { ADMIN_COOKIE } from "@/lib/admin-server";
import { API_URL } from "@/lib/server";
import { hasSameOrigin, readLimitedBody, trustedClientIp } from "@/lib/request-security";

/** Forward a bounded, same-origin admin write without exposing the admin token to JavaScript. */
export async function adminPost(request: NextRequest, backendPath: string) {
  if (!hasSameOrigin(request)) return NextResponse.json({ detail: "Invalid request origin." }, { status: 403 });
  let body: string;
  try { body = await readLimitedBody(request, 4096); }
  catch { return NextResponse.json({ detail: "Request is too large." }, { status: 413 }); }
  const token = (await cookies()).get(ADMIN_COOKIE)?.value;
  if (!token) return NextResponse.json({ detail: "Sign in to continue." }, { status: 401 });
  try {
    const response = await fetch(`${API_URL}/api/v1/admin${backendPath}`, {
      method: "POST", headers: { "Content-Type": "application/json", Authorization: `AdminBearer ${token}`,
        "X-Forwarded-For": trustedClientIp(request) },
      body, cache: "no-store", signal: AbortSignal.timeout(10000),
    });
    const text = await response.text();
    return new NextResponse(text || null, { status: response.status,
      headers: { "Content-Type": "application/json", "Cache-Control": "no-store",
        "X-Request-ID": response.headers.get("X-Request-ID") ?? "" } });
  } catch {
    return NextResponse.json({ detail: "The admin service is unavailable." }, { status: 503 });
  }
}
