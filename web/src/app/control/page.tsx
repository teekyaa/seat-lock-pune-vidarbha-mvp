import Link from "next/link";
import { redirect } from "next/navigation";
import { adminApi, AdminApiError } from "@/lib/admin-server";
import { Overview } from "./Overview";
import { FeatureFlags } from "./FeatureFlags";

export default async function ControlHome() {
  try {
    const admin = await adminApi("/api/v1/admin/me");
    if (!admin.permissions.includes("overview:read")) {
      return <p role="alert" className="py-8">Your account cannot view the overview.</p>;
    }
    const overview = await adminApi("/api/v1/admin/overview");
    let flags = null;
    if (admin.permissions.includes("feature_flags:read")) {
      try { flags = await adminApi("/api/v1/admin/feature-flags"); }
      catch { flags = null; }
    }
    return <><Overview initial={overview} />
      {admin.permissions.includes("audit_logs:read") && <p className="mt-5"><Link className="control-button inline-block" href="/control/audit">View audit log</Link></p>}
      {admin.permissions.includes("feature_flags:read") && <FeatureFlags initial={flags}
        canToggle={admin.permissions.includes("feature_flags:toggle")}
        canToggleCritical={admin.permissions.includes("feature_flags:toggle_critical")} />}</>;
  } catch (error) {
    if (error instanceof AdminApiError && error.status === 401) redirect("/control/login");
    return <div className="control-card mt-8 p-5"><p role="alert">The admin service is unavailable.</p>
      <Link href="/control" className="mt-3 inline-block underline">Try again</Link></div>;
  }
}
