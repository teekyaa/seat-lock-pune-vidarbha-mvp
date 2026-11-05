import { cookies } from "next/headers";
import { API_URL } from "./server";
import type { components, paths } from "./admin-api.generated";

export const ADMIN_COOKIE = "sl_admin_session";

export type AdminIdentity = components["schemas"]["AdminIdentity"];
export type AdminOverview = components["schemas"]["AdminOverview"];
export type FeatureFlag = components["schemas"]["FeatureFlag"];
export type FeatureFlagChange = components["schemas"]["FeatureFlagChange"];
type AdminGetPath = "/api/v1/admin/me" | "/api/v1/admin/overview" | "/api/v1/admin/feature-flags" | "/api/v1/admin/audit-logs";
type AdminGetResponse<P extends AdminGetPath> = paths[P]["get"]["responses"][200]["content"]["application/json"];

export class AdminApiError extends Error {
  constructor(public status: number, message: string) { super(message); }
}

export async function adminApi<P extends AdminGetPath>(path: P, options: { background?: boolean; query?: URLSearchParams } = {}): Promise<AdminGetResponse<P>> {
  const token = (await cookies()).get(ADMIN_COOKIE)?.value;
  if (!token) throw new AdminApiError(401, "Sign in to continue.");
  let response: Response;
  try {
    const query = options.query?.toString();
    response = await fetch(`${API_URL}${path}${query ? `?${query}` : ""}`, {
      headers: { Authorization: `AdminBearer ${token}`, ...(options.background ? { "X-Admin-Background": "1" } : {}) },
      cache: "no-store", signal: AbortSignal.timeout(10000),
    });
  } catch {
    throw new AdminApiError(503, "The admin service is unavailable. Try again.");
  }
  if (!response.ok) throw new AdminApiError(response.status, "The admin service could not complete your request.");
  return response.json() as Promise<AdminGetResponse<P>>;
}

export async function adminFlagHistory(key: string): Promise<FeatureFlagChange[]> {
  const token = (await cookies()).get(ADMIN_COOKIE)?.value;
  if (!token) throw new AdminApiError(401, "Sign in to continue.");
  let response: Response;
  try {
    response = await fetch(`${API_URL}/api/v1/admin/feature-flags/${encodeURIComponent(key)}/history`, {
      headers: { Authorization: `AdminBearer ${token}` }, cache: "no-store", signal: AbortSignal.timeout(10000),
    });
  } catch { throw new AdminApiError(503, "The admin service is unavailable."); }
  if (!response.ok) throw new AdminApiError(response.status, "Unable to load control history.");
  return response.json() as Promise<FeatureFlagChange[]>;
}
