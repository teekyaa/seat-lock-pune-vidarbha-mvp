"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { ActionBar } from "@/components/ActionBar";
import { PhoneIcon } from "@/components/icons";
import { ConfirmSheet, Sheet } from "@/components/Sheet";
import { call, istInputToIso } from "@/lib/client";
import type { Booking, Ride } from "@/lib/types";
import { ShareButton } from "./ShareButtons";

const ACTIVE = ["requested", "accepted", "advance_claimed", "confirmed"];

type Pending = { kind: "confirm-advance" | "decline"; booking: Booking } | { kind: "cancel-ride" } | null;

export function DriverPanel({ ride, bookings, waitlist, shareUrl }: {
  ride: Ride; bookings: Booking[]; waitlist: { id: number; passenger: string; status: string }[]; shareUrl: string;
}) {
  const router = useRouter();
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [pending, setPending] = useState<Pending>(null);
  const [manageOpen, setManageOpen] = useState(false);
  const [newTime, setNewTime] = useState("");
  const active = bookings.filter((b) => ACTIVE.includes(b.status));
  const requests = active.filter((b) => b.status === "requested");
  const holding = active.filter((b) => b.status !== "requested");
  const past = bookings.filter((b) => !ACTIVE.includes(b.status));

  async function run(fn: () => Promise<unknown>) {
    setBusy(true);
    setError("");
    try {
      await fn();
      setPending(null);
      setManageOpen(false);
      router.refresh();
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setBusy(false);
    }
  }

  const Passenger = ({ b }: { b: Booking }) => {
    const r = b.passenger.reliability;
    return (
      <li className="card space-y-3">
        <div className="flex items-start justify-between gap-2">
          <Link href={`/u/${b.passenger.id}`} className="min-w-0">
            <p className="font-bold">{b.passenger.name}</p>
            <p className="text-sm text-muted">
              From {b.passenger.hometown}. {r.completed_trips} trip{r.completed_trips === 1 ? "" : "s"}
              {r.passenger_late_cancellations > 0 && `, ${r.passenger_late_cancellations} late cancel`}
              {r.no_shows > 0 && `, ${r.no_shows} no-show`}
            </p>
          </Link>
          <span className={`pill shrink-0 ${b.status === "confirmed" ? "bg-mile text-ink" : "bg-paper text-muted"}`}>
            {b.status === "confirmed" ? "Locked" : b.status_label}
          </span>
        </div>
        {b.note && <p className="rounded-xl bg-paper p-3 text-sm">&ldquo;{b.note}&rdquo;</p>}
        {b.status === "requested" && <p className="text-sm text-muted">Reply by {b.request_expires_at?.ist}</p>}
        {b.status === "accepted" && <p className="text-sm text-muted">Waiting for ₹{b.advance_inr}. Hold ends {b.hold_expires_at?.ist}.</p>}
        {b.status === "advance_claimed" && (
          <p className="rounded-xl bg-mile-wash p-3 text-sm">Says they paid ₹{b.advance_inr}. Check your UPI app before you confirm.</p>
        )}
        {b.at_risk && <p className="rounded-xl bg-warn-wash p-3 text-sm text-warn">Hasn&apos;t reconfirmed yet. Give them a call.</p>}
        <div className="flex flex-wrap gap-2">
          {b.actions.includes("accept") && (
            <button className="btn-primary flex-1" disabled={busy} onClick={() => run(() => call(`/bookings/${b.code}/accept`, "POST"))}>Accept</button>
          )}
          {b.actions.includes("decline") && (
            <button className="btn-secondary flex-1" disabled={busy} onClick={() => setPending({ kind: "decline", booking: b })}>Decline</button>
          )}
          {b.actions.includes("confirm-advance") && (
            <button className="btn-primary flex-1" disabled={busy} onClick={() => setPending({ kind: "confirm-advance", booking: b })}>Advance received</button>
          )}
          {b.contact && (
            <a href={`tel:${b.contact.phone}`} className="btn-secondary flex-1"><PhoneIcon /> Call</a>
          )}
          <Link href={`/bookings/${b.code}`} className="btn-ghost">Details</Link>
        </div>
      </li>
    );
  };

  return (
    <div className="mt-5 space-y-5">
      {requests.length > 0 && (
        <section>
          <h2 className="mb-2 text-lg font-bold">Requests ({requests.length})</h2>
          <ul className="space-y-3">{requests.map((b) => <Passenger key={b.code} b={b} />)}</ul>
        </section>
      )}

      <section>
        <h2 className="mb-2 text-lg font-bold">Passengers</h2>
        {holding.length === 0 ? (
          <p className="card text-sm text-muted">Nobody yet. Share the ride in your WhatsApp group so people can book.</p>
        ) : (
          <ul className="space-y-3">{holding.map((b) => <Passenger key={b.code} b={b} />)}</ul>
        )}
      </section>

      {waitlist.length > 0 && (
        <section className="card">
          <h2 className="mb-2 text-base font-bold">Waitlist</h2>
          <ol className="list-decimal space-y-1 pl-5 text-sm">
            {waitlist.map((w) => <li key={w.id}>{w.passenger}{w.status === "offered" && " (offered a seat)"}</li>)}
          </ol>
        </section>
      )}

      {past.length > 0 && (
        <details className="card text-sm">
          <summary className="min-h-8 cursor-pointer font-semibold">Earlier requests ({past.length})</summary>
          <ul className="mt-2 space-y-2">
            {past.map((b) => (
              <li key={b.code}><Link href={`/bookings/${b.code}`} className="underline">{b.passenger.name}</Link>: {b.status_label}</li>
            ))}
          </ul>
        </details>
      )}

      {error && <p className="text-sm text-danger" role="alert">{error}</p>}

      <ActionBar>
        {ride.status === "open" ? (
          <ShareButton url={shareUrl} text={`${ride.origin} to ${ride.destination}, ${ride.departure_at.ist}. ₹${ride.fare_inr} a seat. Book on Seat Lock:`} variant="button" />
        ) : (
          <p className="py-2 text-center text-base font-semibold text-muted">This ride is {ride.status}.</p>
        )}
        {ride.status === "open" && (
          <button className="mt-1 min-h-10 w-full text-sm font-semibold text-muted" onClick={() => setManageOpen(true)}>
            Change time or cancel ride
          </button>
        )}
      </ActionBar>

      <ConfirmSheet
        open={pending?.kind === "confirm-advance"}
        onClose={() => setPending(null)}
        title="Advance received?"
        confirmLabel={`Yes, ₹${pending && pending.kind !== "cancel-ride" ? pending.booking.advance_inr : ""} is in my account`}
        busy={busy}
        onConfirm={() => pending && pending.kind === "confirm-advance" && run(() => call(`/bookings/${pending.booking.code}/confirm-advance`, "POST"))}
        body={pending && pending.kind === "confirm-advance" && (
          <>
            <p>Open your UPI app and check that ₹{pending.booking.advance_inr} from {pending.booking.passenger.name} has arrived, with note {pending.booking.code}.</p>
            <p className="text-sm text-muted">This locks their seat. Your phone number and car number become visible to them.</p>
          </>
        )}
      />
      <ConfirmSheet
        open={pending?.kind === "decline"}
        onClose={() => setPending(null)}
        title="Decline this request?"
        confirmLabel="Decline"
        danger
        busy={busy}
        onConfirm={() => pending && pending.kind === "decline" && run(() => call(`/bookings/${pending.booking.code}/decline`, "POST"))}
        body={<p>They&apos;ll be told you can&apos;t take them, so they can look for another ride.</p>}
      />
      <ConfirmSheet
        open={pending?.kind === "cancel-ride"}
        onClose={() => setPending(null)}
        title="Cancel this ride?"
        confirmLabel="Cancel ride"
        danger
        busy={busy}
        onConfirm={() => run(() => call(`/rides/${ride.code}/cancel`, "POST"))}
        body={
          <>
            <p>Everyone who paid gets their full advance back from you within 24 hours.</p>
            <p>If departure is less than 48 hours away, this counts as a late cancellation on your public record. Two in one festival season pause your posting until the season ends.</p>
          </>
        }
      />

      <Sheet open={manageOpen} onClose={() => setManageOpen(false)} title="Change or cancel">
        <div className="space-y-4">
          <div>
            <label className="label" htmlFor="newtime">New departure time (IST)</label>
            <input id="newtime" type="datetime-local" className="field" value={newTime} onChange={(e) => setNewTime(e.target.value)} />
            <p className="hint">Moving it by more than 2 hours lets confirmed passengers cancel with a full refund, and shows on your record.</p>
          </div>
          <button className="btn-primary w-full" disabled={busy || !newTime}
            onClick={() => run(() => call(`/rides/${ride.code}`, "PATCH", { departure_at: istInputToIso(newTime) }))}>
            Save new time
          </button>
          <hr className="border-line" />
          <button className="btn-danger w-full" onClick={() => { setManageOpen(false); setPending({ kind: "cancel-ride" }); }}>Cancel this ride</button>
          {error && <p className="text-sm text-danger" role="alert">{error}</p>}
        </div>
      </Sheet>
    </div>
  );
}
