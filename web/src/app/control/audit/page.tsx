import Link from "next/link";
import { redirect } from "next/navigation";
import { adminApi, AdminApiError } from "@/lib/admin-server";

const fields = ["action", "resource_type", "resource_id", "admin_id", "from", "to"] as const;
type Search = Record<string, string | string[] | undefined>;

export default async function AuditPage({ searchParams }: { searchParams: Promise<Search> }) {
  const params = await searchParams;
  const query = new URLSearchParams();
  for (const key of [...fields, "cursor"] as const) {
    const value = params[key];
    if (typeof value === "string" && value.length <= 2000) query.set(key, value);
  }
  try {
    const admin = await adminApi("/api/v1/admin/me");
    if (!admin.permissions.includes("audit_logs:read")) {
      return <p role="alert" className="py-8">Your account cannot view the audit log.</p>;
    }
    const page = await adminApi("/api/v1/admin/audit-logs", { query });
    const next = new URLSearchParams(query);
    if (page.next_cursor) next.set("cursor", page.next_cursor);
    return <section className="py-6 space-y-5">
      <Link href="/control" className="underline">← Overview</Link>
      <div><h1 className="text-2xl font-bold">Audit log</h1>
        <p className="control-muted">Administrative activity. Sensitive values are redacted.</p></div>
      <form className="control-card p-4 grid gap-3 sm:grid-cols-2 lg:grid-cols-3" action="/control/audit">
        {fields.map((field) => <label key={field} className="text-sm font-semibold">{field.replaceAll("_", " ")}
          <input className="control-input mt-1" name={field} defaultValue={typeof params[field] === "string" ? params[field] : ""}
            placeholder={field === "from" || field === "to" ? "2026-11-05T00:00:00+05:30" : undefined} />
        </label>)}
        <div className="flex items-end gap-3"><button className="control-button" type="submit">Apply filters</button>
          <Link href="/control/audit" className="underline">Clear</Link></div>
      </form>
      {page.results.length === 0 && <p>No matching activity.</p>}
      <div className="space-y-3">{page.results.map((entry) => <article key={entry.id} className="control-card p-4 space-y-2">
        <div className="flex flex-wrap justify-between gap-2"><h2 className="font-bold">{entry.action}</h2>
          <time dateTime={entry.created_at} className="control-muted text-sm">{new Date(entry.created_at).toLocaleString("en-IN", { timeZone: "Asia/Kolkata" })} IST</time></div>
        <p className="text-sm">{entry.admin_name || "System or unidentified admin"} · {entry.admin_role || "No role"}</p>
        <p className="text-sm break-all">{entry.resource_type || "Activity"}{entry.resource_id && ` · ${entry.resource_id}`}</p>
        {entry.reason && <p className="text-sm">Reason: {entry.reason}</p>}
        {(entry.before != null || entry.after != null) && <details><summary className="cursor-pointer text-sm">Change details</summary>
          <pre className="overflow-auto text-xs whitespace-pre-wrap break-all">{JSON.stringify({ before: entry.before, after: entry.after }, null, 2)}</pre></details>}
        <p className="control-muted text-xs break-all">Request ID: {entry.request_id}</p>
      </article>)}</div>
      {page.next_cursor && <Link className="control-button inline-block" href={`/control/audit?${next.toString()}`}>Next page</Link>}
    </section>;
  } catch (error) {
    if (error instanceof AdminApiError && error.status === 401) redirect("/control/login");
    return <div className="control-card mt-8 p-5"><p role="alert">{error instanceof AdminApiError && error.status === 400
      ? "Check the filters. Dates must include a timezone, for example +05:30." : "The audit log is unavailable."}</p>
      <Link href="/control/audit" className="mt-3 inline-block underline">Clear filters and try again</Link></div>;
  }
}
