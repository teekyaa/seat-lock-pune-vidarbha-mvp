import { NextRequest, NextResponse } from "next/server";
import { adminApi, AdminApiError } from "@/lib/admin-server";

export async function GET(request: NextRequest) {
  try {
    const flags = await adminApi("/api/v1/admin/feature-flags", {
      background: request.nextUrl.searchParams.get("background") === "1",
    });
    return NextResponse.json(flags, { headers: { "Cache-Control": "no-store" } });
  } catch (error) {
    return NextResponse.json({ detail: "Unable to load control status." }, {
      status: error instanceof AdminApiError ? error.status : 503,
    });
  }
}
