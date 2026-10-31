"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { ActionBar } from "@/components/ActionBar";
import { PolicyTimeline } from "@/components/PolicyTimeline";
import { Sheet } from "@/components/Sheet";
import { call } from "@/lib/client";
import type { Booking, Ride } from "@/lib/types";

/** Passenger's sticky action bar on a ride, and the request / waitlist sheets behind it. */
export function RideActions({ ride, signedIn, profileComplete }: { ride: Ride; signedIn: boolean; profileComplete: boolean }) {
  const router = useRouter();
  const [open, setOpen] = useState(false);
  const [note, setNote] = useState("");
  const [ack, setAck] = useState(false);
  const [seatRole, setSeatRole] = useState<"passenger" | "co_driver">("passenger");
  const [licenceAck, setLicenceAck] = useState(false);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const viewer = ride.viewer;
  const here = `/r/${ride.code}`;
  const offer = viewer?.waitlist;
  const isOffer = offer?.status === "offered";
  const isWaitlist = !isOffer && ride.seats_left === 0;

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

  const price = (
    <div className="min-w-0">
      <p className="text-xl font-extrabold leading-tight tabular-nums">₹{ride.fare_inr.toLocaleString("en-IN")}</p>
      <p className="text-xs text-muted">₹{ride.advance_inr} advance locks it</p>
    </div>
  );

  let bar: React.ReactNode;
  if (ride.status !== "open") {
    bar = <p className="py-2 text-center text-base font-semibold text-muted">This ride isn&apos;t taking bookings.</p>;
  } else if (!signedIn) {
    bar = <div className="flex items-center gap-3">{price}<Link href={`/login?next=${here}`} className="btn-primary ml-auto flex-1">Sign in to book</Link></div>;
  } else if (!profileComplete) {
    bar = <Link href={`/me?next=${here}`} className="btn-primary w-full">Finish your profile to book</Link>;
  } else if (viewer?.booking_code) {
    bar = <Link href={`/bookings/${viewer.booking_code}`} className="btn-primary w-full">Open your booking</Link>;
  } else if (offer?.status === "offered") {
    bar = (
      <div className="space-y-2">
        <p className="text-center text-sm font-semibold">A seat opened for you. Take it by {offer.offer_expires_at?.ist}.</p>
        <button className="btn-primary w-full bg-ink" onClick={() => setOpen(true)}>Take the seat</button>
      </div>
    );
  } else if (offer?.status === "waiting") {
    bar = (
      <div className="flex items-center gap-3">
        <p className="flex-1 text-sm">You&apos;re on the {offer.role === "co_driver" ? "co-driver " : ""}waitlist. We&apos;ll offer you the next free seat.</p>
        <button className="btn-secondary" disabled={busy} onClick={() => run(async () => {
          await call(`/waitlist/${offer.id}/withdraw`, "POST");
          router.refresh();
        })}>Leave</button>
      </div>
    );
  } else if (ride.seats_left === 0) {
    bar = (
      <div className="flex items-center gap-3">{price}
        <button className="btn-primary ml-auto flex-1" onClick={() => { setError(""); setOpen(true); }}>Join waitlist</button>
      </div>
    );
  } else {
    bar = <div className="flex items-center gap-3">{price}<button className="btn-primary ml-auto flex-1" onClick={() => setOpen(true)}>Request a seat</button></div>;
  }

  return (
    <>
      <ActionBar>
        {bar}
        {error && !open && <p className="mt-2 text-center text-sm text-danger" role="alert">{error}</p>}
      </ActionBar>

      <Sheet open={open} onClose={() => setOpen(false)} title={isOffer ? "Take this seat" : isWaitlist ? "Join the waitlist" : "Request a seat"}>
        <form className="space-y-5" onSubmit={(e) => {
          e.preventDefault();
          run(async () => {
            if (isOffer) {
              const b = await call<Booking>(`/waitlist/${offer!.id}/accept`, "POST", { policy_ack: ack });
              router.push(`/bookings/${b.code}`);
            } else if (isWaitlist) {
              await call(`/rides/${ride.code}/waitlist`, "POST", { role: seatRole, co_driver_license_ack: seatRole === "co_driver" && licenceAck });
              setOpen(false);
              router.refresh();
            } else {
              const b = await call<Booking>(`/rides/${ride.code}/request`, "POST", { note, policy_ack: ack, role: seatRole, co_driver_license_ack: seatRole === "co_driver" && licenceAck });
              router.push(`/bookings/${b.code}`);
            }
          });
        }}>
          {isWaitlist ? (
            <p className="text-sm text-muted">We&apos;ll offer you a seat if one opens. You&apos;ll have a limited time to accept; joining the waitlist does not reserve a seat.</p>
          ) : (
            <ol className="space-y-3">
              {[
                isOffer ? "The seat is held for you now." : `${ride.driver.name.split(" ")[0]} accepts or declines. If they don't reply in time, the request lapses.`,
                `You pay the ₹${ride.advance_inr} advance straight to them over UPI within ${ride.policy?.hold_hours ?? 2} hours.`,
                "They mark it received and your seat is locked. You'll see their number and the car then.",
              ].map((t, i) => (
                <li key={t} className="flex gap-3 text-sm">
                  <span className="grid h-6 w-6 shrink-0 place-items-center rounded-full bg-mile text-xs font-bold">{i + 1}</span>
                  <span className="pt-0.5">{t}</span>
                </li>
              ))}
            </ol>
          )}

          {ride.codriver_wanted && !isOffer && (
            <fieldset className="space-y-3">
              <legend className="label">How would you like to travel?</legend>
              <label className="flex min-h-12 items-center gap-3 rounded-xl bg-surface px-4 ring-1 ring-line"><input type="radio" name="seat-role" checked={seatRole === "passenger"} onChange={() => setSeatRole("passenger")} className="h-5 w-5 accent-brand" />Passenger</label>
              <label className="flex min-h-12 items-center gap-3 rounded-xl bg-surface px-4 ring-1 ring-line"><input type="radio" name="seat-role" checked={seatRole === "co_driver"} onChange={() => setSeatRole("co_driver")} className="h-5 w-5 accent-brand" />Co-driver · share driving</label>
              {seatRole === "co_driver" && <div className="space-y-2 rounded-xl bg-paper p-3"><label className="flex items-start gap-3 text-sm"><input type="checkbox" checked={licenceAck} onChange={(e) => setLicenceAck(e.target.checked)} className="mt-0.5 h-5 w-5 accent-brand" /><span>I have a valid driving licence and agree to share driving. This is self-attested and has not been verified.</span></label><p className="text-xs text-muted">Same listed fare and cancellation policy apply in this prototype.</p></div>}
            </fieldset>
          )}
          {!isOffer && !isWaitlist && (
            <div>
              <label className="label" htmlFor="note">Message to the driver (optional)</label>
              <textarea id="note" className="field" rows={2} maxLength={300} value={note} onChange={(e) => setNote(e.target.value)}
                placeholder="Hi! One backpack. Drop near Sitabuldi if possible." />
            </div>
          )}

          {!isWaitlist && ride.cutoffs && (
            <div className="rounded-2xl bg-paper p-4">
              <p className="mb-3 text-sm font-bold">If plans change</p>
              <PolicyTimeline cutoffs={ride.cutoffs} advance={ride.advance_inr} />
            </div>
          )}

          {!isWaitlist && <label className="flex min-h-12 items-start gap-3 text-base">
            <input type="checkbox" checked={ack} onChange={(e) => setAck(e.target.checked)} className="mt-1 h-5 w-5 accent-brand" />
            <span>I agree to these cancellation times.</span>
          </label>}
          {error && <p className="text-sm text-danger" role="alert">{error}</p>}
          <button className="btn-primary w-full" disabled={busy || (isWaitlist ? seatRole === "co_driver" && !licenceAck : !ack || (seatRole === "co_driver" && !licenceAck))}>
            {busy ? "Sending" : isOffer ? "Take the seat" : isWaitlist ? "Join waitlist" : "Send request"}
          </button>
        </form>
      </Sheet>
    </>
  );
}
