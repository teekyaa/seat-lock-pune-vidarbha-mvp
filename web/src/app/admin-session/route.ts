import { cookies } from "next/headers";
import { NextRequest, NextResponse } from "next/server";
import { ADMIN_COOKIE } from "@/lib/admin-server";
import { API_URL } from "@/lib/server";
import { hasSameOrigin, readLimitedBody, trustedClientIp } from "@/lib/request-security";

export async function POST(request: NextRequest) {
  if (!hasSameOrigin(request)) return NextResponse.json({ detail: "Invalid request origin." }, { status: 403 });
  let body: string;
  try { body = await readLimitedBody(request, 4096); }
  catch { return NextResponse.json({ detail: "Request is too large." }, { status: 413 }); }
  let input: unknown;
  try { input = JSON.parse(body); }
  catch { return NextResponse.json({ detail: "Invalid request." }, { status: 400 }); }
  let response: Response;
  try {
    response = await fetch(`${API_URL}/api/v1/admin/auth/login`, {
      method: "POST", headers: { "Content-Type": "application/json", "X-Forwarded-For": trustedClientIp(request) },
      body: JSON.stringify(input), cache: "no-store", signal: AbortSignal.timeout(10000),
    });
  } catch { return NextResponse.json({ detail: "Admin sign-in is unavailable." }, { status: 503 }); }
  const data: unknown = await response.json().catch(() => null);
  if (!response.ok) {
    const nested = data && typeof data === "object" && "error" in data ? data.error : null;
    const detail = nested && typeof nested === "object" && "message" in nested && typeof nested.message === "string"
      ? nested.message : "Admin sign-in is unavailable.";
    return NextResponse.json({ detail }, { status: response.status });
  }
  if (!data || typeof data !== "object" || !("token" in data) || typeof data.token !== "string") {
    return NextResponse.json({ detail: "Admin sign-in is unavailable." }, { status: 502 });
  }
  (await cookies()).set(ADMIN_COOKIE, data.token, {
    httpOnly: true, secure: process.env.NODE_ENV === "production", sameSite: "strict", path: "/", maxAge: 12 * 60 * 60,
  });
  return NextResponse.json({ ok: true });
}

export async function DELETE(request: NextRequest) {
  if (!hasSameOrigin(request)) return NextResponse.json({ detail: "Invalid request origin." }, { status: 403 });
  const jar = await cookies();
  const token = jar.get(ADMIN_COOKIE)?.value;
  if (token) {
    try {
      const response = await fetch(`${API_URL}/api/v1/admin/auth/logout`, {
        method: "POST", headers: { Authorization: `AdminBearer ${token}` }, cache: "no-store", signal: AbortSignal.timeout(10000),
      });
      if (!response.ok && response.status !== 401) throw new Error("Logout failed");
    } catch { return NextResponse.json({ detail: "Could not sign out. Please try again." }, { status: 503 }); }
  }
  jar.delete(ADMIN_COOKIE);
  return new NextResponse(null, { status: 204 });
}
