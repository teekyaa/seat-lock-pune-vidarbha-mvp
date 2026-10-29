"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";
import { ActionBar } from "@/components/ActionBar";
import { MoreIcon, PhoneIcon } from "@/components/icons";
import { ConfirmSheet, Sheet } from "@/components/Sheet";
import { TopBar } from "@/components/TopBar";
import { call } from "@/lib/client";
import type { Booking } from "@/lib/types";

const REASONS: [string, string][] = [
  ["unsafe_driving", "Unsafe driving"],
  ["harassment", "Harassment"],
  ["misleading_ride", "Ride not as described"],
  ["payment_dispute", "Payment problem"],
  ["no_show", "No-show"],
  ["other", "Something else"],
];

type Sheets = "more" | "cancel" | "report" | "block" | "confirm-advance" | "no-show" | "decline" | null;

/**
 * Owns everything interactive on a booking: the header, the one next step for this person,
 * the sticky primary action, and the "More" sheet for rarer actions.
 */
export function BookingActions({ booking: b, children }: { booking: Booking; children: React.ReactNode }) {
  const router = useRouter();
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [busy, setBusy] = useState(false);
  const [sheet, setSheet] = useState<Sheets>(null);
  const [utr, setUtr] = useState("");
  const [statement, setStatement] = useState("");
  const [reason, setReason] = useState("other");
  const [details, setDetails] = useState("");
  const has = (a: string) => b.actions.includes(a);
  const reconfirm = b.actions.find((a) => a.startsWith("reconfirm-"));
  const stage = reconfirm ? Number(reconfirm.split("-")[1]) : 0;
  const first = (n: string) => n.split(" ")[0];
  const other = b.role === "driver" ? b.passenger.name : b.ride.driver.name;

  async function act(action: string, body?: unknown) {
    setBusy(true);
    setError("");
    setNotice("");
    try {
      const res = await call<{ detail?: string }>(`/bookings/${b.code}/${action}`, "POST", body ?? {});
      if (res?.detail) setNotice(res.detail);
      setSheet(null);
      router.refresh();
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setBusy(false);
    }
  }

  const cancelConsequence = () => {
    if (b.status !== "confirmed") return b.status === "advance_claimed" ? "You marked the advance as paid, so the driver owes it all back." : "Nothing is lost, you haven't paid yet.";
    if (b.free_cancel_any_time) return "The driver moved the departure, so your full advance comes back.";
    const now = Date.now();
    if (b.cutoffs && now < Date.parse(b.cutoffs.full_refund_until.utc)) return `You get all ₹${b.advance_inr} back within 24 hours.`;
    const half = b.advance_inr - Math.floor(b.advance_inr / 2);
    if (b.cutoffs && now < Date.parse(b.cutoffs.full_penalty_from.utc))
      return `The driver keeps half. You get ₹${half} back, or all of it if someone takes your seat before departure.`;
    return "The driver keeps the whole advance, unless someone takes your seat before departure.";
  };

  // The single most important thing this person should do now.
  let next: React.ReactNode = null;
  let primary: React.ReactNode = null;

  if (b.role === "passenger" && b.pay && has("claim-advance")) {
    next = (
      <div className="space-y-3">
        <p className="text-lg font-bold">Pay ₹{b.pay.amount_inr} to lock your seat</p>
        <p className="text-sm text-muted">Pay by <b className="text-ink">{b.pay.pay_by.ist}</b> or the seat is released. The money goes straight to {first(b.ride.driver.name)}. Seat Lock never touches it.</p>
        <p className="text-sm text-muted">Paid already? Tell {first(b.ride.driver.name)} so they can check.</p>
        <input className="field" inputMode="numeric" placeholder="UPI reference number (optional)" value={utr}
          onChange={(e) => setUtr(e.target.value.replace(/\D/g, ""))} maxLength={22} aria-label="UPI reference number" />
        <button className="btn-secondary w-full" disabled={busy} onClick={() => act("claim-advance", { utr })}>I&apos;ve paid</button>
      </div>
    );
    primary = <a href={b.pay.upi_link} className="btn-primary w-full">Pay ₹{b.pay.amount_inr} with UPI app</a>;
  } else if (b.role === "passenger" && b.status === "requested") {
    next = <p className="text-base">Waiting for {first(b.ride.driver.name)} to reply. They have until <b>{b.request_expires_at?.ist}</b>.</p>;
  } else if (b.role === "passenger" && b.status === "advance_claimed") {
    next = <p className="text-base">You marked the advance as paid. Your seat locks once {first(b.ride.driver.name)} sees it arrive.</p>;
  } else if (b.role === "driver" && has("accept")) {
    next = <p className="text-base">{b.passenger.name} wants a seat. Reply by <b>{b.request_expires_at?.ist}</b>.</p>;
    primary = (
      <div className="grid grid-cols-2 gap-2">
        <button className="btn-secondary" disabled={busy} onClick={() => setSheet("decline")}>Decline</button>
        <button className="btn-primary" disabled={busy} onClick={() => act("accept")}>Accept</button>
      </div>
    );
  } else if (b.role === "driver" && has("confirm-advance")) {
    next = <p className="text-base">{b.status === "advance_claimed" ? `${first(b.passenger.name)} says they paid ₹${b.advance_inr}.` : `Waiting for ₹${b.advance_inr} from ${first(b.passenger.name)}.`} Check your UPI app.</p>;
    primary = <button className="btn-primary w-full" disabled={busy} onClick={() => setSheet("confirm-advance")}>Advance received</button>;
  } else if (reconfirm) {
    next = <p className="text-lg font-bold">{b.role === "passenger" ? "Still coming?" : "Still driving?"}</p>;
    primary = (
      <div className="grid grid-cols-2 gap-2">
        <button className="btn-secondary" disabled={busy} onClick={() => act("reconfirm", { stage_hours: stage, coming: false })}>Not sure</button>
        <button className="btn-primary" disabled={busy} onClick={() => act("reconfirm", { stage_hours: stage, coming: true })}>Yes, I&apos;m in</button>
      </div>
    );
  } else if (has("trip-confirmation")) {
    next = <p className="text-lg font-bold">Did this trip happen?</p>;
    primary = (
      <div className="grid grid-cols-2 gap-2">
        <button className="btn-secondary" disabled={busy} onClick={() => act("trip-confirmation", { happened: false })}>No</button>
        <button className="btn-primary" disabled={busy} onClick={() => act("trip-confirmation", { happened: true })}>Yes, it did</button>
      </div>
    );
  } else if (b.refund_pay) {
    next = <p className="text-base">Send ₹{b.refund_pay.amount_inr} back to {first(b.passenger.name)} by <b>{b.refund?.due_at.ist}</b>.</p>;
    primary = <a href={b.refund_pay.upi_link} className="btn-primary w-full">Refund ₹{b.refund_pay.amount_inr} with UPI app</a>;
  } else if (has("refund-received")) {
    next = <p className="text-base">Has ₹{b.refund?.amount_inr} come back from {first(b.ride.driver.name)}?</p>;
    primary = <button className="btn-primary w-full" disabled={busy} onClick={() => act("refund-received")}>Yes, refund received</button>;
  } else if (has("dispute-no-show") && b.no_show) {
    next = (
      <div className="space-y-3">
        <p className="text-lg font-bold">Marked as a no-show</p>
        <p className="text-sm text-muted">If you were there, tell us by {b.no_show.dispute_until.ist}. Our team reviews it.</p>
        <textarea className="field" rows={3} value={statement} onChange={(e) => setStatement(e.target.value)} placeholder="Where were you, and when?" aria-label="What happened" />
      </div>
    );
    primary = <button className="btn-primary w-full" disabled={busy} onClick={() => act("dispute-no-show", { statement })}>Dispute no-show</button>;
  } else if (b.status === "confirmed") {
    next = <p className="text-base">Your seat is locked. {b.role === "passenger" ? "See you at pickup." : "Have a safe drive."}</p>;
  }

  if (!primary && b.contact) {
    primary = <a href={`tel:${b.contact.phone}`} className="btn-primary w-full"><PhoneIcon /> Call {first(other)}</a>;
  }

  return (
    <>
      <TopBar
        title="Booking"
        fallback="/bookings"
        trailing={
          <button aria-label="More actions" className="grid h-12 w-12 place-items-center rounded-full active:bg-line/60" onClick={() => setSheet("more")}>
            <MoreIcon />
          </button>
        }
      />
      {children}

      {next && <section className="mt-3 rounded-2xl bg-mile-wash p-4">{next}</section>}

      {b.contact && (
        <section className="card mt-3 space-y-1 text-sm">
          <p><span className="text-muted">Phone </span><a href={`tel:${b.contact.phone}`} className="font-bold underline underline-offset-4">{b.contact.phone}</a></p>
          {b.contact.registration && <p><span className="text-muted">Car </span><b>{b.contact.registration}</b></p>}
          {b.contact.pickup_details && <p><span className="text-muted">Pickup </span>{b.contact.pickup_details}</p>}
        </section>
      )}

      {has("no-show") && (
        <button className="btn-danger mt-3 w-full" onClick={() => setSheet("no-show")}>{first(b.passenger.name)} didn&apos;t turn up</button>
      )}

      {notice && <p className="mt-3 rounded-xl bg-brand-wash p-3 text-sm text-brand" role="status">{notice}</p>}
      {error && !sheet && <p className="mt-3 text-sm text-danger" role="alert">{error}</p>}

      {primary && <ActionBar>{primary}</ActionBar>}

      <Sheet open={sheet === "more"} onClose={() => setSheet(null)} title="More">
        <div className="grid gap-2">
          {has("cancel") && <button className="btn-danger w-full" onClick={() => setSheet("cancel")}>Cancel booking</button>}
          {has("report") && <button className="btn-secondary w-full" onClick={() => setSheet("report")}>Report a problem</button>}
          {has("block") && <button className="btn-secondary w-full" onClick={() => setSheet("block")}>Block {first(other)}</button>}
          {!has("cancel") && !has("report") && !has("block") && <p className="text-base text-muted">Nothing else to do here right now.</p>}
        </div>
      </Sheet>

      <ConfirmSheet open={sheet === "cancel"} onClose={() => setSheet(null)} title="Cancel this booking?" danger busy={busy}
        confirmLabel="Cancel booking" onConfirm={() => act("cancel")}
        body={<><p className="text-lg font-semibold">{cancelConsequence()}</p>{error && <p className="text-sm text-danger">{error}</p>}</>} />

      <ConfirmSheet open={sheet === "decline"} onClose={() => setSheet(null)} title="Decline this request?" danger busy={busy}
        confirmLabel="Decline" onConfirm={() => act("decline")}
        body={<p>{first(b.passenger.name)} will be told, so they can look for another ride.</p>} />

      <ConfirmSheet open={sheet === "confirm-advance"} onClose={() => setSheet(null)} title="Advance received?" busy={busy}
        confirmLabel={`Yes, ₹${b.advance_inr} is in my account`} onConfirm={() => act("confirm-advance")}
        body={<>
          <p>Check your UPI app for ₹{b.advance_inr} from {b.passenger.name}, note {b.code}.</p>
          <p className="text-sm text-muted">This locks their seat and shares your phone number and car number with them.</p>
        </>} />

      <ConfirmSheet open={sheet === "no-show"} onClose={() => setSheet(null)} title="Mark as a no-show?" danger busy={busy}
        confirmLabel="Mark no-show" onConfirm={() => act("no-show")}
        body={<p>{first(b.passenger.name)} has 24 hours to dispute it. If they don&apos;t, you keep the advance and it shows on their record.</p>} />

      <ConfirmSheet open={sheet === "block"} onClose={() => setSheet(null)} title={`Block ${first(other)}?`} danger busy={busy}
        confirmLabel="Block" onConfirm={() => act("block")}
        body={<p>You won&apos;t see each other&apos;s rides again. This booking isn&apos;t changed.</p>} />

      <Sheet open={sheet === "report"} onClose={() => setSheet(null)} title="Report a problem">
        <div className="space-y-4">
          <fieldset className="grid gap-2">
            <legend className="label">What happened?</legend>
            {REASONS.map(([v, l]) => (
              <label key={v} className={`flex min-h-12 items-center gap-3 rounded-xl px-3 ring-1 ${reason === v ? "bg-brand-wash ring-brand" : "ring-line"}`}>
                <input type="radio" name="reason" value={v} checked={reason === v} onChange={() => setReason(v)} className="h-5 w-5 accent-brand" />
                {l}
              </label>
            ))}
          </fieldset>
          <textarea className="field" rows={3} maxLength={1000} value={details} onChange={(e) => setDetails(e.target.value)}
            placeholder="Tell us more. Only our team sees this." aria-label="Details" />
          {error && <p className="text-sm text-danger" role="alert">{error}</p>}
          <button className="btn-primary w-full" disabled={busy} onClick={() => act("report", { reason, details })}>Send report</button>
        </div>
      </Sheet>
    </>
  );
}
