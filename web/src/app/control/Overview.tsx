"use client";

import { useCallback, useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import type { AdminOverview } from "@/lib/admin-server";

const ist = new Intl.DateTimeFormat("en-IN", { timeZone: "Asia/Kolkata", dateStyle: "medium", timeStyle: "medium" });

export function Overview({ initial }: { initial: AdminOverview }) {
  const router = useRouter();
  const [data, setData] = useState(initial);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  const refresh = useCallback(async (background = false) => {
    setBusy(true);
    try {
      const response = await fetch(`/admin-api/overview${background ? "?background=1" : ""}`,
        { cache: "no-store", signal: AbortSignal.timeout(10000) });
      if (response.status === 401) { router.replace("/control/login"); return; }
      if (!response.ok) throw new Error("Overview unavailable");
      setData(await response.json() as AdminOverview);
      setError("");
    } catch {
      setError("Could not refresh. Showing the last available counts.");
    } finally { setBusy(false); }
  }, [router]);

  useEffect(() => {
    const timer = setInterval(() => { void refresh(true); }, 30000);
    return () => clearInterval(timer);
  }, [refresh]);

  const metrics = [
    { label: "Rides scheduled today", value: data.rides_scheduled_today },
    { label: "Rides in next 24 hours", value: data.rides_next_24_hours },
    { label: "Reserved seats", value: data.held_seats, note: "Includes confirmed seats on upcoming rides" },
    { label: "Open reports", value: data.open_reports, note: "Existing reports; ticket queues are not yet available" },
    { label: "New signups today", value: data.new_signups_today },
  ];
  return (
    <div className="py-8">
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div><p className="control-muted text-sm font-semibold">Operations overview</p><h1 className="text-3xl font-extrabold">Command center</h1>
          <p className="control-muted mt-1 text-sm">Last updated {ist.format(new Date(data.as_of))} IST</p></div>
        <button className="control-button" disabled={busy} onClick={() => void refresh()}>{busy ? "Refreshing…" : "Refresh"}</button>
      </div>
      {error && <p role="alert" className="mt-4 rounded-xl bg-amber-100 p-3 text-amber-950">{error}</p>}
      <div className="mt-6 grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
        {metrics.map((metric) => <div key={metric.label} className="control-card p-5">
          <p className="control-muted text-sm font-semibold">{metric.label}</p>
          <p className="mt-2 text-3xl font-extrabold tabular-nums">{metric.value.toLocaleString("en-IN")}</p>
          {metric.note && <p className="control-muted mt-2 text-xs">{metric.note}</p>}
        </div>)}
      </div>
      <section className="control-card mt-5 p-5">
        <h2 className="text-lg font-bold">Not available yet</h2>
        <p className="control-muted mt-2 text-sm">Support ticket queues, risk flags, payment gateway metrics, alerts and operational controls are not implemented. Payment records in Seat Lock are participant claims and obligations.</p>
      </section>
    </div>
  );
}
