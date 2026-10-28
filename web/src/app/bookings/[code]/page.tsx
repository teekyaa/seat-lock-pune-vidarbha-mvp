import Link from "next/link";
import { notFound, redirect } from "next/navigation";
import { ApiError, api, getMe } from "@/lib/server";
import type { Booking } from "@/lib/types";
import { BookingActions } from "./BookingActions";

export const metadata = { title: "Booking" };

const OUTCOME: Record<string, string> = {
  full: "Full advance comes back",
  half: "Driver keeps half, the rest comes back",
  none: "Driver keeps the advance",
  pending_refill: "Decided at departure, or sooner if your seat is refilled",
};

export default async function BookingPage({ params }: { params: Promise<{ code: string }> }) {
  const { code } = await params;
  const me = await getMe();
  if (!me) redirect(`/login?next=/bookings/${code}`);
  let b: Booking;
  try {
    b = await api<Booking>(`/bookings/${encodeURIComponent(code)}`);
  } catch (e) {
    if (e instanceof ApiError && (e.status === 404 || e.status === 403)) notFound();
    throw e;
  }
  const other = b.role === "driver" ? b.passenger.name : b.ride.driver.name;

  return (
    <div className="space-y-4">
      <Link href={`/r/${b.ride_code}`} className="text-sm text-brand">Back to the ride</Link>
      <section className="card space-y-2">
        <div className="flex items-start justify-between gap-3">
          <div>
            <h1 className="text-xl font-bold">{b.ride.origin} to {b.ride.destination}</h1>
            <p className="text-sm text-muted">{b.ride.departure_at.ist}</p>
          </div>
          <span className="pill bg-brand-wash text-brand">{b.status_label}</span>
        </div>
        <dl className="grid grid-cols-2 gap-3 text-sm">
          <div><dt className="text-muted">Booking code</dt><dd className="font-mono font-semibold">{b.code}</dd></div>
          <div><dt className="text-muted">{b.role === "driver" ? "Passenger" : "Driver"}</dt><dd className="font-medium">{other}</dd></div>
          <div><dt className="text-muted">Fare</dt><dd className="font-medium">₹{b.fare_inr}</dd></div>
          <div><dt className="text-muted">Advance</dt><dd className="font-medium">₹{b.advance_inr}</dd></div>
        </dl>
        {b.contact && (
          <div className="rounded-xl border border-brand/30 bg-brand-wash p-3 text-sm">
            <p>Phone: <a href={`tel:${b.contact.phone}`} className="font-semibold underline">{b.contact.phone}</a></p>
            {b.contact.registration && <p>Car: {b.contact.registration}</p>}
            {b.contact.pickup_details && <p>Pickup: {b.contact.pickup_details}</p>}
          </div>
        )}
        {b.at_risk && <p className="rounded-xl bg-warn-wash p-3 text-sm text-warn">This seat hasn&apos;t been reconfirmed yet.</p>}
      </section>

      <BookingActions booking={b} />

      {(b.refund_outcome || b.refund) && (
        <section className="card space-y-1 text-sm">
          <h2 className="font-bold">Refund</h2>
          {b.refund_outcome && <p>{OUTCOME[b.refund_outcome]}{b.refund_inr ? `: ₹${b.refund_inr}` : ""}.</p>}
          {b.refund && (
            <p className="text-muted">
              {b.refund.status === "confirmed"
                ? `Received, confirmed on ${b.refund.confirmed_at?.ist}.`
                : `₹${b.refund.amount_inr} due from the driver by ${b.refund.due_at.ist}.${b.refund.overdue ? " It is overdue and shows on the driver's record." : ""}`}
            </p>
          )}
        </section>
      )}

      <section className="card space-y-2 text-sm">
        <h2 className="font-bold">Cancellation times for this booking</h2>
        {b.free_cancel_any_time ? (
          <p>The driver moved the departure, so you can cancel with a full refund any time before it leaves.</p>
        ) : b.cutoffs && (
          <ul className="space-y-1">
            <li>Before <b>{b.cutoffs.full_refund_until.ist}</b>: full advance back.</li>
            <li>Until <b>{b.cutoffs.full_penalty_from.ist}</b>: driver keeps half.</li>
            <li>After that, or a no-show: driver keeps it all. A refilled seat always gets a full refund.</li>
          </ul>
        )}
        <p className="text-xs text-muted">Agreed under policy {b.policy.label}. Later policy changes don&apos;t apply to this booking.</p>
      </section>
    </div>
  );
}
