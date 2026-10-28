"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { call, istInputToIso } from "@/lib/client";
import type { Booking, Ride } from "@/lib/types";

const ACTIVE = ["requested", "accepted", "advance_claimed", "confirmed"];

export function DriverPanel({ ride, bookings, waitlist }: {
  ride: Ride; bookings: Booking[]; waitlist: { id: number; passenger: string; status: string }[];
}) {
  const router = useRouter();
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [newTime, setNewTime] = useState("");
  const active = bookings.filter((b) => ACTIVE.includes(b.status));
  const past = bookings.filter((b) => !ACTIVE.includes(b.status));

  async function run(fn: () => Promise<unknown>) {
    setBusy(true);
    setError("");
    try {
      await fn();
      router.refresh();
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="space-y-4">
      <section className="card space-y-3">
        <h2 className="font-bold">Passengers</h2>
        {active.length === 0 && <p className="text-sm text-muted">No requests yet. Share the ride in your WhatsApp group.</p>}
        {active.map((b) => (
          <div key={b.code} className="space-y-2 rounded-xl bg-paper p-3 text-sm">
            <div className="flex items-center justify-between">
              <Link href={`/u/${b.passenger.id}`} className="font-semibold">{b.passenger.name}</Link>
              <span className="pill bg-white">{b.status_label}</span>
            </div>
            <p className="text-xs text-muted">
              From {b.passenger.hometown} · {b.passenger.reliability.completed_trips} trips
              {b.passenger.reliability.passenger_late_cancellations > 0 && ` · ${b.passenger.reliability.passenger_late_cancellations} late cancellations`}
              {b.passenger.reliability.no_shows > 0 && ` · ${b.passenger.reliability.no_shows} no-shows`}
            </p>
            {b.note && <p>&ldquo;{b.note}&rdquo;</p>}
            {b.status === "requested" && <p className="text-xs text-muted">Reply by {b.request_expires_at?.ist}</p>}
            {b.status === "accepted" && <p className="text-xs text-muted">Waiting for ₹{b.advance_inr} by {b.hold_expires_at?.ist}</p>}
            {b.status === "advance_claimed" && <p className="text-xs text-warn">Says they paid ₹{b.advance_inr}. Check your UPI app first.</p>}
            {b.at_risk && <p className="text-xs text-warn">Hasn&apos;t reconfirmed. Give them a call.</p>}
            {b.contact && <p>Phone: <a className="font-semibold underline" href={`tel:${b.contact.phone}`}>{b.contact.phone}</a></p>}
            <div className="flex flex-wrap gap-2">
              {b.actions.includes("accept") && (
                <button className="btn-primary min-h-9" disabled={busy} onClick={() => run(() => call(`/bookings/${b.code}/accept`, "POST"))}>Accept</button>
              )}
              {b.actions.includes("decline") && (
                <button className="btn-secondary min-h-9" disabled={busy} onClick={() => run(() => call(`/bookings/${b.code}/decline`, "POST"))}>Decline</button>
              )}
              {b.actions.includes("confirm-advance") && (
                <button className="btn-primary min-h-9" disabled={busy} onClick={() => {
                  if (confirm(`Only tap this once ₹${b.advance_inr} from ${b.passenger.name} is in your account.`)) {
                    run(() => call(`/bookings/${b.code}/confirm-advance`, "POST"));
                  }
                }}>Advance received</button>
              )}
              <Link href={`/bookings/${b.code}`} className="btn-secondary min-h-9">Details</Link>
            </div>
          </div>
        ))}
        {past.length > 0 && (
          <details className="text-sm">
            <summary className="cursor-pointer text-muted">Earlier requests ({past.length})</summary>
            <ul className="mt-2 space-y-1">
              {past.map((b) => (
                <li key={b.code}><Link href={`/bookings/${b.code}`} className="underline">{b.passenger.name}</Link>: {b.status_label}</li>
              ))}
            </ul>
          </details>
        )}
      </section>

      {waitlist.length > 0 && (
        <section className="card space-y-2 text-sm">
          <h2 className="font-bold">Waitlist</h2>
          <ol className="list-decimal pl-5">
            {waitlist.map((w) => <li key={w.id}>{w.passenger} · {w.status}</li>)}
          </ol>
        </section>
      )}

      {ride.status === "open" && (
        <section className="card space-y-3 text-sm">
          <h2 className="font-bold">Change or cancel</h2>
          <div className="flex gap-2">
            <input type="datetime-local" className="field" value={newTime} onChange={(e) => setNewTime(e.target.value)} aria-label="New departure (IST)" />
            <button className="btn-secondary" disabled={busy || !newTime} onClick={() => {
              if (confirm("Moving departure by more than 2 hours lets confirmed passengers cancel with a full refund, and shows on your record.")) {
                run(() => call(`/rides/${ride.code}`, "PATCH", { departure_at: istInputToIso(newTime) }));
              }
            }}>Move</button>
          </div>
          <button className="btn-danger w-full" disabled={busy} onClick={() => {
            if (confirm("Cancel this ride? Every passenger who paid gets their full advance back from you within 24 hours. Under 48 hours before departure this is a late cancellation on your record.")) {
              run(() => call(`/rides/${ride.code}/cancel`, "POST"));
            }
          }}>Cancel ride</button>
        </section>
      )}
      {error && <p className="text-sm text-danger" role="alert">{error}</p>}
    </div>
  );
}
