import { cookies } from "next/headers";
import { NextRequest, NextResponse } from "next/server";
import { API_URL, TOKEN_COOKIE } from "@/lib/server";
import { hasSameOrigin, readLimitedBody, trustedClientIp } from "@/lib/request-security";

// Same-origin proxy so the session token stays in an httpOnly cookie and never reaches page JavaScript.
async function forward(req: NextRequest, { params }: { params: Promise<{ path: string[] }> }) {
  if (!["GET", "HEAD"].includes(req.method) && !hasSameOrigin(req)) {
    return NextResponse.json({ detail: "Invalid request origin." }, { status: 403 });
  }
  const { path } = await params;
  const token = (await cookies()).get(TOKEN_COOKIE)?.value;
  const url = `${API_URL}/api/v1/${path.map(encodeURIComponent).join("/")}${req.nextUrl.search}`;
  let body: string | undefined;
  try {
    body = ["GET", "HEAD"].includes(req.method) ? undefined : await readLimitedBody(req);
  } catch {
    return NextResponse.json({ detail: "Request is too large." }, { status: 413 });
  }
  const res = await fetch(url, {
    method: req.method,
    headers: {
      "Content-Type": "application/json",
      "X-Forwarded-For": trustedClientIp(req),
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
    },
    body: body || undefined,
    cache: "no-store",
  });
  const text = await res.text();
  return new NextResponse(text || null, {
    status: res.status,
    headers: { "Content-Type": res.headers.get("Content-Type") ?? "application/json" },
  });
}

export { forward as GET, forward as POST, forward as PATCH, forward as DELETE };
