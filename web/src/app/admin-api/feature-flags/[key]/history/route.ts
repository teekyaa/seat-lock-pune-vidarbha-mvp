import { NextResponse } from "next/server";
import { adminFlagHistory, AdminApiError } from "@/lib/admin-server";

export async function GET(_request: Request, { params }: { params: Promise<{ key: string }> }) {
  try {
    const { key } = await params;
    return NextResponse.json(await adminFlagHistory(key), { headers: { "Cache-Control": "no-store" } });
  } catch (error) {
    return NextResponse.json({ detail: "Unable to load control history." }, {
      status: error instanceof AdminApiError ? error.status : 503,
    });
  }
}
