import { NextRequest, NextResponse } from "next/server";
import { adminApi, AdminApiError } from "@/lib/admin-server";

export async function GET(request: NextRequest) {
  try {
    return NextResponse.json(await adminApi("/api/v1/admin/overview", {
      background: request.nextUrl.searchParams.get("background") === "1",
    }), { headers: { "Cache-Control": "no-store" } });
  } catch (error) {
    const status = error instanceof AdminApiError ? error.status : 503;
    return NextResponse.json({ detail: "Unable to load the overview." }, { status });
  }
}
