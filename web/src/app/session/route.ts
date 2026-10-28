import { cookies } from "next/headers";
import { NextRequest, NextResponse } from "next/server";
import { API_URL, TOKEN_COOKIE } from "@/lib/server";

/** Verify the OTP with the API and keep the token in an httpOnly cookie. */
export async function POST(req: NextRequest) {
  const { phone, code } = await req.json();
  const res = await fetch(`${API_URL}/api/v1/auth/otp/verify`, {
    method: "POST",
    headers: { "Content-Type": "application/json", "X-Forwarded-For": req.headers.get("x-forwarded-for") ?? "" },
    body: JSON.stringify({ phone, code }),
  });
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

export async function DELETE() {
  const jar = await cookies();
  const token = jar.get(TOKEN_COOKIE)?.value;
  if (token) {
    await fetch(`${API_URL}/api/v1/auth/logout`, { method: "POST", headers: { Authorization: `Bearer ${token}` } });
  }
  jar.delete(TOKEN_COOKIE);
  return new NextResponse(null, { status: 204 });
}
