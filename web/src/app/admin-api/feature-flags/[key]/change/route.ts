import { NextRequest } from "next/server";
import { adminPost } from "@/lib/admin-proxy";

export async function POST(request: NextRequest, { params }: { params: Promise<{ key: string }> }) {
  const { key } = await params;
  return adminPost(request, `/feature-flags/${encodeURIComponent(key)}/change`);
}
