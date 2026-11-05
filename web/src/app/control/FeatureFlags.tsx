"use client";

import { useState } from "react";
import type { FeatureFlag, FeatureFlagChange } from "@/lib/admin-server";
import type { components } from "@/lib/admin-api.generated";
import { ConfirmActionDialog } from "./ConfirmActionDialog";

type FlagUpdate = components["schemas"]["FeatureFlagUpdate"];
type Reauthentication = components["schemas"]["AdminReauthentication"];

function errorInfo(data: unknown): { code: string; message: string } {
  if (data && typeof data === "object" && "error" in data && data.error && typeof data.error === "object") {
    const error = data.error;
    return { code: "code" in error && typeof error.code === "string" ? error.code : "",
      message: "message" in error && typeof error.message === "string" ? error.message : "Unable to complete the request." };
  }
  if (data && typeof data === "object" && "detail" in data && typeof data.detail === "string") return { code: "", message: data.detail };
  return { code: "", message: "Unable to complete the request." };
}

export function FeatureFlags({ initial, canToggle, canToggleCritical }: {
  initial: FeatureFlag[] | null; canToggle: boolean; canToggleCritical: boolean;
}) {
  const [flags, setFlags] = useState(initial);
  const [selected, setSelected] = useState<FeatureFlag | null>(null);
  const [reason, setReason] = useState("");
  const [confirmation, setConfirmation] = useState("");
  const [password, setPassword] = useState("");
  const [code, setCode] = useState("");
  const [needsReauth, setNeedsReauth] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [history, setHistory] = useState<Record<string, FeatureFlagChange[]>>({});
  const [historyError, setHistoryError] = useState("");

  function close() {
    setSelected(null); setReason(""); setConfirmation(""); setPassword(""); setCode("");
    setNeedsReauth(false); setError("");
  }

  async function changeFlag() {
    if (!selected || busy) return;
    const body: FlagUpdate = { value: !selected.value, reason, confirmation };
    setBusy(true); setError("");
    try {
      const response = await fetch(`/admin-api/feature-flags/${encodeURIComponent(selected.key)}/change`, {
        method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body),
      });
      const data: unknown = await response.json();
      if (!response.ok) {
        const detail = errorInfo(data);
        if (detail.code === "ADMIN_REAUTH_REQUIRED") setNeedsReauth(true);
        throw new Error(detail.message);
      }
      const updated = data as FeatureFlag;
      setFlags((current) => current ? current.map((flag) => flag.key === updated.key ? updated : flag) : current);
      setHistory((current) => { const next = { ...current }; delete next[updated.key]; return next; });
      void readHistory(updated.key);
      window.dispatchEvent(new Event("admin-control-changed"));
      setNotice(`${updated.description} ${updated.value ? "Enabled." : "Paused."}`);
      close();
    } catch (failure) { setError(failure instanceof Error ? failure.message : "Unable to update the control."); }
    finally { setBusy(false); }
  }

  async function readHistory(key: string) {
    setHistoryError("");
    try {
      const response = await fetch(`/admin-api/feature-flags/${encodeURIComponent(key)}/history`, { cache: "no-store" });
      if (!response.ok) throw new Error("Unable to load control history.");
      const entries = await response.json() as FeatureFlagChange[];
      setHistory((current) => ({ ...current, [key]: entries }));
    } catch { setHistoryError("Unable to load control history. Try again."); }
  }

  async function reauthenticate() {
    if (busy) return;
    const body: Reauthentication = { password, code };
    setBusy(true); setError("");
    try {
      const response = await fetch("/admin-session/reauthenticate", {
        method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body),
      });
      if (!response.ok) throw new Error(errorInfo(await response.json()).message);
      setNeedsReauth(false); setNotice("Identity confirmed. Review the control change and confirm it again.");
    } catch (failure) { setError(failure instanceof Error ? failure.message : "Unable to verify your identity."); }
    finally { setPassword(""); setCode(""); setBusy(false); }
  }

  return <section className="pb-8" aria-labelledby="operational-controls-title">
    <h2 id="operational-controls-title" className="text-xl font-extrabold">Operational controls</h2>
    <p className="control-muted mt-1 text-sm">These switches affect new activity. Requests already in progress may still complete.</p>
    {notice && <p role="status" className="control-card mt-3 p-3 text-sm">{notice}</p>}
    {historyError && <p role="alert" className="control-card mt-3 p-3 text-sm">{historyError}</p>}
    {flags === null ? <p role="alert" className="control-card mt-3 p-4">Controls are unavailable. Refresh to try again.</p> :
      flags.length === 0 ? <p className="control-card mt-3 p-4">No controls are available.</p> :
      <div className="mt-3 grid gap-3 md:grid-cols-2">{flags.map((flag) => <article key={flag.key} className="control-card p-5">
        <div className="flex flex-wrap items-start justify-between gap-3"><div>
          <h3 className="font-bold">{flag.description}</h3><p className="control-muted mt-1 break-all text-xs">{flag.key}</p>
          <p className="mt-3 text-sm font-semibold">Status: {flag.value ? "Enabled" : "Paused"}</p>
          {flag.updated_by && <p className="control-muted mt-1 text-xs">Last changed by {flag.updated_by}</p>}
        </div>{(flag.is_critical ? canToggleCritical : canToggle) && <button className="control-button" onClick={() => { setNotice(""); setSelected(flag); }}>
          {flag.value ? "Pause" : "Resume"}</button>}</div>
        <details className="mt-4 text-sm" onToggle={(event) => { if (event.currentTarget.open) void readHistory(flag.key); }}>
          <summary className="cursor-pointer font-semibold">Recent history</summary>
          {history[flag.key] === undefined ? <p className="control-muted mt-2">Loading history…</p> :
            history[flag.key].length === 0 ? <p className="control-muted mt-2">No changes yet.</p> :
            <ul className="mt-2 space-y-2">{history[flag.key].map((entry) => <li key={entry.id} className="rounded-lg border p-2" style={{ borderColor: "var(--control-line)" }}>
              <p>{entry.old_value ? "Enabled" : "Paused"} → {entry.new_value ? "Enabled" : "Paused"} by {entry.changed_by}</p>
              <p className="control-muted text-xs">{new Intl.DateTimeFormat("en-IN", { timeZone: "Asia/Kolkata", dateStyle: "medium", timeStyle: "short" }).format(new Date(entry.created_at))} IST</p>
              {entry.reason && <p className="control-muted mt-1">Reason: {entry.reason}</p>}
              {(flag.is_critical ? canToggleCritical : canToggle) && entry.old_value !== flag.value && <button className="control-button mt-2 text-xs" onClick={() => { setNotice(""); setSelected(flag); }}>Restore previous value</button>}
            </li>)}</ul>}
        </details>
      </article>)}</div>}
    <ConfirmActionDialog open={selected !== null} busy={busy} onClose={close}>
      {selected && <div className="space-y-4">
        <h2 id="confirm-action-title" className="text-xl font-extrabold">{selected.value ? "Pause" : "Resume"} this control?</h2>
        <p className="control-muted text-sm">{selected.key.startsWith("bookings.")
          ? selected.value ? "New requests and waitlist acceptance will pause. Existing bookings remain active; waitlist offers may expire while paused."
            : "New requests and waitlist acceptance will resume. The scheduler will resume eligible waitlists."
          : selected.key.startsWith("rides.") ? selected.value ? "New ride posting will pause. Existing rides remain available."
            : "Drivers will be able to post new rides again."
          : selected.value ? "New user registrations will pause. Existing users can still sign in. The change can take up to 30 seconds to reach all workers."
            : "New user registrations will resume. The change can take up to 30 seconds to reach all workers."}</p>
        <p className="control-muted text-sm">Requests already in progress may still complete.</p>
        <label className="block text-sm font-semibold">Reason <textarea className="control-input mt-1" rows={2} maxLength={1000}
          value={reason} onChange={(event) => setReason(event.target.value)} /></label>
        <label className="block text-sm font-semibold">Type <span className="break-all">{selected.key}</span> to confirm
          <input className="control-input mt-1" value={confirmation} onChange={(event) => setConfirmation(event.target.value)} /></label>
        {needsReauth && <div className="space-y-3 rounded-xl border p-3" style={{ borderColor: "var(--control-line)" }}>
          <p className="text-sm font-bold">Verify your identity using a new authenticator code.</p>
          <label className="block text-sm font-semibold">Password<input className="control-input mt-1" type="password" autoComplete="current-password"
            value={password} onChange={(event) => setPassword(event.target.value)} /></label>
          <label className="block text-sm font-semibold">Authenticator code<input className="control-input mt-1" inputMode="numeric"
            autoComplete="one-time-code" maxLength={6} value={code} onChange={(event) => setCode(event.target.value.replace(/\D/g, "").slice(0, 6))} /></label>
          <button className="control-button" disabled={busy || !password || code.length !== 6} onClick={() => void reauthenticate()}>Verify identity</button>
        </div>}
        {error && <p role="alert" className="rounded-xl bg-red-100 p-3 text-sm text-red-900">{error}</p>}
        <div className="flex flex-wrap justify-end gap-2"><button className="control-button" disabled={busy} onClick={close}>Cancel</button>
          <button className="rounded-xl bg-green-800 px-4 py-3 font-bold text-white disabled:opacity-50"
            disabled={busy || needsReauth || reason.trim().length < 3 || confirmation !== selected.key} onClick={() => void changeFlag()}>
            {busy ? "Saving…" : "Confirm change"}</button></div>
      </div>}
    </ConfirmActionDialog>
  </section>;
}
