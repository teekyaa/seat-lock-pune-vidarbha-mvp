"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";
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

export function BookingActions({ booking: b }: { booking: Booking }) {
  const router = useRouter();
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [busy, setBusy] = useState(false);
  const [utr, setUtr] = useState("");
  const [statement, setStatement] = useState("");
  const [reportOpen, setReportOpen] = useState(false);
  const [reason, setReason] = useState("other");
  const [details, setDetails] = useState("");
  const has = (a: string) => b.actions.includes(a);
  const reconfirm = b.actions.find((a) => a.startsWith("reconfirm-"));

  async function act(action: string, body?: unknown, confirmText?: string) {
    if (confirmText && !confirm(confirmText)) return;
    setBusy(true);
    setError("");
    setNotice("");
    try {
      const res = await call<{ detail?: string }>(`/bookings/${b.code}/${action}`, "POST", body ?? {});
      if (res?.detail) setNotice(res.detail);
      router.refresh();
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setBusy(false);
    }
  }

  const cancelText = () => {
    if (b.status !== "confirmed" || b.free_cancel_any_time) return "Cancel this booking?";
    const now = Date.now();
    if (b.cutoffs && now < Date.parse(b.cutoffs.full_refund_until.utc)) return "Cancel? You get your full advance back.";
    if (b.cutoffs && now < Date.parse(b.cutoffs.full_penalty_from.utc))
      return "Cancel? The driver keeps half your advance unless your seat is refilled before departure.";
    return "Cancel? The driver keeps your whole advance unless your seat is refilled before departure.";
  };

  return (
    <section className="space-y-3">
      {b.status === "requested" && b.role === "passenger" && (
        <p className="card text-sm">Waiting for the driver. They have until {b.request_expires_at?.ist} to reply.</p>
      )}

      {b.pay && has("claim-advance") && (
        <div className="card space-y-3 border-brand">
          <h2 className="font-bold">Pay ₹{b.pay.amount_inr} to lock your seat</h2>
          <p className="text-sm text-muted">
            Pay by <b>{b.pay.pay_by.ist}</b> or the hold lapses. The money goes straight to {b.ride.driver.name}. Seat Lock never touches it.
          </p>
          <a href={b.pay.upi_link} className="btn-primary w-full">Pay with a UPI app</a>
          <p className="text-xs text-muted">On a computer? Open this page on your phone, or pay {b.ride.driver.name} by UPI and use booking code {b.code} as the note.</p>
          <input className="field" placeholder="UPI reference number (optional)" value={utr} onChange={(e) => setUtr(e.target.value.replace(/\D/g, ""))} maxLength={22} />
          <button className="btn-secondary w-full" disabled={busy} onClick={() => act("claim-advance", { utr })}>I&apos;ve paid</button>
        </div>
      )}
      {b.status === "advance_claimed" && b.role === "passenger" && (
        <p className="card text-sm">You marked the advance as paid. Your seat is confirmed once {b.ride.driver.name} sees it arrive.</p>
      )}

      {b.role === "driver" && (has("accept") || has("confirm-advance")) && (
        <div className="card flex flex-wrap gap-2">
          {has("accept") && <button className="btn-primary" disabled={busy} onClick={() => act("accept")}>Accept</button>}
          {has("decline") && <button className="btn-secondary" disabled={busy} onClick={() => act("decline")}>Decline</button>}
          {has("confirm-advance") && (
            <button className="btn-primary" disabled={busy} onClick={() => act("confirm-advance", {}, `Only confirm once ₹${b.advance_inr} is in your account.`)}>
              Advance received
            </button>
          )}
        </div>
      )}

      {reconfirm && (
        <div className="card space-y-2">
          <h2 className="font-bold">{b.role === "passenger" ? "Still coming?" : "Still driving?"}</h2>
          <div className="flex gap-2">
            <button className="btn-primary flex-1" disabled={busy} onClick={() => act("reconfirm", { stage_hours: Number(reconfirm.split("-")[1]), coming: true })}>Yes</button>
            <button className="btn-secondary flex-1" disabled={busy} onClick={() => act("reconfirm", { stage_hours: Number(reconfirm.split("-")[1]), coming: false })}>Not sure</button>
          </div>
        </div>
      )}

      {has("trip-confirmation") && (
        <div className="card space-y-2">
          <h2 className="font-bold">Did this trip happen?</h2>
          <div className="flex gap-2">
            <button className="btn-primary flex-1" disabled={busy} onClick={() => act("trip-confirmation", { happened: true })}>Yes</button>
            <button className="btn-secondary flex-1" disabled={busy} onClick={() => act("trip-confirmation", { happened: false })}>No</button>
          </div>
        </div>
      )}

      {has("no-show") && (
        <button className="btn-danger w-full" disabled={busy} onClick={() => act("no-show", {}, `Mark ${b.passenger.name} as a no-show? They have 24 hours to dispute it.`)}>
          Passenger didn&apos;t turn up
        </button>
      )}
      {has("dispute-no-show") && b.no_show && (
        <div className="card space-y-2">
          <h2 className="font-bold">Your driver marked you as a no-show</h2>
          <p className="text-sm text-muted">If you were there, tell us by {b.no_show.dispute_until.ist}. Our team will look into it.</p>
          <textarea className="field" rows={2} value={statement} onChange={(e) => setStatement(e.target.value)} placeholder="What happened?" />
          <button className="btn-primary w-full" disabled={busy} onClick={() => act("dispute-no-show", { statement })}>Dispute</button>
        </div>
      )}

      {b.refund_pay && (
        <div className="card space-y-2">
          <h2 className="font-bold">Send the refund</h2>
          <p className="text-sm text-muted">₹{b.refund_pay.amount_inr} back to {b.passenger.name} by {b.refund?.due_at.ist}.</p>
          <a href={b.refund_pay.upi_link} className="btn-primary w-full">Refund with a UPI app</a>
        </div>
      )}
      {has("refund-received") && (
        <button className="btn-primary w-full" disabled={busy} onClick={() => act("refund-received")}>Refund received</button>
      )}

      {has("cancel") && (
        <button className="btn-danger w-full" disabled={busy} onClick={() => act("cancel", {}, cancelText())}>Cancel booking</button>
      )}

      {(has("report") || has("block")) && (
        <div className="flex gap-2 text-sm">
          {has("report") && <button className="text-muted underline" onClick={() => setReportOpen(!reportOpen)}>Report a problem</button>}
          {has("block") && (
            <button className="text-muted underline" onClick={() => act("block", {}, "Block this person? You won't see each other's rides again.")}>Block</button>
          )}
        </div>
      )}
      {reportOpen && (
        <div className="card space-y-2">
          <select className="field" value={reason} onChange={(e) => setReason(e.target.value)}>
            {REASONS.map(([v, l]) => <option key={v} value={v}>{l}</option>)}
          </select>
          <textarea className="field" rows={3} maxLength={1000} value={details} onChange={(e) => setDetails(e.target.value)} placeholder="Tell us what happened. Only our team sees this." />
          <button className="btn-primary w-full" disabled={busy} onClick={async () => { await act("report", { reason, details }); setReportOpen(false); }}>Send report</button>
        </div>
      )}

      {notice && <p className="text-sm text-brand">{notice}</p>}
      {error && <p className="text-sm text-danger" role="alert">{error}</p>}
    </section>
  );
}
