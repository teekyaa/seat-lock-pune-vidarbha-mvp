"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { call } from "@/lib/client";
import type { Booking, Ride } from "@/lib/types";

export function RideActions({ ride, signedIn, profileComplete }: { ride: Ride; signedIn: boolean; profileComplete: boolean }) {
  const router = useRouter();
  const [note, setNote] = useState("");
  const [ack, setAck] = useState(false);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const viewer = ride.viewer;
  const here = `/r/${ride.code}`;

  async function run(fn: () => Promise<void>) {
    setBusy(true);
    setError("");
    try {
      await fn();
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setBusy(false);
    }
  }

  if (ride.status !== "open") return null;
  if (!signedIn) {
    return (
      <div className="card space-y-2 text-sm">
        <p>Sign in with your phone number to request a seat.</p>
        <Link href={`/login?next=${here}`} className="btn-primary w-full">Sign in to book</Link>
      </div>
    );
  }
  if (!profileComplete) {
    return (
      <div className="card text-sm">
        <Link href={`/me?next=${here}`} className="btn-primary w-full">Finish your profile to book</Link>
      </div>
    );
  }
  if (viewer?.booking_code) {
    return (
      <div className="card text-sm">
        <Link href={`/bookings/${viewer.booking_code}`} className="btn-primary w-full">Open your booking</Link>
      </div>
    );
  }

  const policyBox = (
    <label className="flex items-start gap-2 text-sm">
      <input type="checkbox" checked={ack} onChange={(e) => setAck(e.target.checked)} className="mt-1" />
      <span>I agree to the cancellation policy below, with these exact times.</span>
    </label>
  );

  const offer = viewer?.waitlist;
  if (offer?.status === "offered") {
    return (
      <div className="card space-y-3 border-brand">
        <p className="font-semibold text-brand">A seat opened up for you. Accept by {offer.offer_expires_at?.ist}.</p>
        {policyBox}
        <button className="btn-primary w-full" disabled={busy || !ack} onClick={() => run(async () => {
          const b = await call<Booking>(`/waitlist/${offer.id}/accept`, "POST", { policy_ack: ack });
          router.push(`/bookings/${b.code}`);
        })}>Take the seat</button>
        <button className="btn-secondary w-full" disabled={busy} onClick={() => run(async () => {
          await call(`/waitlist/${offer.id}/withdraw`, "POST");
          router.refresh();
        })}>No thanks</button>
        {error && <p className="text-sm text-danger" role="alert">{error}</p>}
      </div>
    );
  }
  if (offer?.status === "waiting") {
    return (
      <div className="card space-y-2 text-sm">
        <p>You&apos;re on the waitlist. If a seat opens, we&apos;ll offer it to you first in line.</p>
        <button className="btn-secondary w-full" disabled={busy} onClick={() => run(async () => {
          await call(`/waitlist/${offer.id}/withdraw`, "POST");
          router.refresh();
        })}>Leave the waitlist</button>
      </div>
    );
  }

  if (ride.seats_left === 0) {
    return (
      <div className="card space-y-2 text-sm">
        <p>This ride is full. Join the waitlist and you&apos;ll get a timed offer if a seat opens.</p>
        <button className="btn-primary w-full" disabled={busy} onClick={() => run(async () => {
          await call(`/rides/${ride.code}/waitlist`, "POST");
          router.refresh();
        })}>Join the waitlist</button>
        {error && <p className="text-danger" role="alert">{error}</p>}
      </div>
    );
  }

  return (
    <form className="card space-y-3" onSubmit={(e) => {
      e.preventDefault();
      run(async () => {
        const b = await call<Booking>(`/rides/${ride.code}/request`, "POST", { note, policy_ack: ack });
        router.push(`/bookings/${b.code}`);
      });
    }}>
      <h2 className="font-bold">Request a seat</h2>
      <textarea className="field" rows={2} maxLength={300} value={note} onChange={(e) => setNote(e.target.value)}
        placeholder="Say hello. Mention luggage or where you'd like to be dropped." />
      <p className="text-xs text-muted">
        If the driver accepts, you&apos;ll have {ride.policy?.hold_hours ?? 2} hours to pay the ₹{ride.advance_inr} advance over UPI.
        Requests close at {ride.requests_close_at?.ist}.
      </p>
      {policyBox}
      {error && <p className="text-sm text-danger" role="alert">{error}</p>}
      <button className="btn-primary w-full" disabled={busy || !ack}>{busy ? "Sending" : "Send request"}</button>
    </form>
  );
}
