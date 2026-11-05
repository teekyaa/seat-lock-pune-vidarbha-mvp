import { NextRequest } from "next/server";
import { adminPost } from "@/lib/admin-proxy";

export async function POST(request: NextRequest) {
  return adminPost(request, "/auth/reauthenticate");
}
