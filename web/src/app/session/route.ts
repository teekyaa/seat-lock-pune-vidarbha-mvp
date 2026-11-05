import { cookies } from "next/headers";
import { NextRequest, NextResponse } from "next/server";
import { API_URL, TOKEN_COOKIE } from "@/lib/server";
import { hasSameOrigin, readLimitedBody, trustedClientIp } from "@/lib/request-security";

/** Verify the OTP with the API and keep the token in an httpOnly cookie. */
export async function POST(req: NextRequest) {
  if (!hasSameOrigin(req)) return NextResponse.json({ detail: "Invalid request origin." }, { status: 403 });
  let body: string;
  try {
    body = await readLimitedBody(req, 4096);
  } catch {
    return NextResponse.json({ detail: "Request is too large." }, { status: 413 });
  }
  let parsed: unknown;
  try {
    parsed = JSON.parse(body);
  } catch {
    return NextResponse.json({ detail: "Invalid request." }, { status: 400 });
  }
  // Valid JSON is not enough: a bare string or array must not reach the API.
  const { phone, code } = (parsed && typeof parsed === "object" && !Array.isArray(parsed) ? parsed : {}) as {
    phone?: unknown; code?: unknown;
  };
  if (typeof phone !== "string" || typeof code !== "string") {
    return NextResponse.json({ detail: "Invalid request." }, { status: 400 });
  }
  let res: Response;
  try {
    res = await fetch(`${API_URL}/api/v1/auth/otp/verify`, {
      method: "POST",
      headers: { "Content-Type": "application/json", "X-Forwarded-For": trustedClientIp(req) },
      body: JSON.stringify({ phone, code }),
    });
  } catch {
    return NextResponse.json({ detail: "Could not reach the server. Please try again." }, { status: 502 });
  }
  const data = await res.json().catch(() => ({}));
  if (!res.ok) return NextResponse.json(data, { status: res.status });
  (await cookies()).set(TOKEN_COOKIE, data.token, {
    httpOnly: true,
    secure: process.env.NODE_ENV === "production",
    sameSite: "lax",
    path: "/",
    maxAge: 60 * 60 * 24 * 30,
  });
  return NextResponse.json({ user: data.user, is_new: data.is_new });
}

export async function DELETE(req: NextRequest) {
  if (!hasSameOrigin(req)) return NextResponse.json({ detail: "Invalid request origin." }, { status: 403 });
  const jar = await cookies();
  const token = jar.get(TOKEN_COOKIE)?.value;
  if (token) {
    await fetch(`${API_URL}/api/v1/auth/logout`, { method: "POST", headers: { Authorization: `Bearer ${token}` } });
  }
  jar.delete(TOKEN_COOKIE);
  return new NextResponse(null, { status: 204 });
}
