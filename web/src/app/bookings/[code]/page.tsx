import Link from "next/link";
import { notFound, redirect } from "next/navigation";
import { PolicyTimeline } from "@/components/PolicyTimeline";
import { RouteMark } from "@/components/RouteMark";
import { Stepper } from "@/components/Stepper";
import { ApiError, api, getMe } from "@/lib/server";
import type { Booking } from "@/lib/types";
import { BookingActions } from "./BookingActions";
import { TripShareCard } from "./TripShareCard";

export const metadata = { title: "Booking" };

const EXIT: Record<string, string> = {
  declined: "The driver couldn't take you on this ride.",
  expired: "The driver didn't reply in time, so the request lapsed.",
  hold_expired: "The advance wasn't marked as paid in time, so the seat was released.",
  cancelled_passenger: "You cancelled this booking.",
  cancelled_driver: "The driver cancelled this ride.",
  no_show: "This booking was marked as a no-show.",
};

const OUTCOME: Record<string, string> = {
  full: "Your full advance comes back",
  half: "The driver keeps half, the rest comes back",
  none: "The driver keeps the advance",
  pending_refill: "Decided at departure, or sooner if someone takes your seat",
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
  const other = b.role === "driver" ? b.passenger : b.ride.driver;
  const exit = b.role === "driver" && b.status === "cancelled_passenger" ? `${b.passenger.name} cancelled this booking.` : EXIT[b.status];

  return (
    <div className="pad-actionbar">
      <BookingActions booking={b}>
        <section className="flex items-center gap-4">
          <RouteMark origin={b.ride.origin} destination={b.ride.destination} km={b.ride.distance_km} />
          <div className="min-w-0">
            <p className="text-sm text-muted">{b.ride.departure_at.ist}</p>
            <p className="text-xl font-extrabold leading-tight">{b.ride.origin} to {b.ride.destination}</p>
            <p className="text-sm text-muted">
              {b.seat_role === "co_driver" ? "Co-driver booking · same listed fare" : "Passenger booking"}{" · "}
              {b.role === "driver" ? "Passenger" : "Driver"}{" "}
              <Link href={`/u/${other.id}`} className="font-semibold text-ink underline decoration-line underline-offset-4">{other.name}</Link>
            </p>
          </div>
        </section>

        <section className="card mt-4">
          {exit ? (
            <p className="text-base font-semibold">{exit}</p>
          ) : (
            <Stepper status={b.status} />
          )}
        </section>
      </BookingActions>

      {(b.refund_outcome || b.refund) && (
        <section className="card mt-3 space-y-1">
          <h2 className="text-base font-bold">Refund</h2>
          {b.refund_outcome && <p className="text-base">{OUTCOME[b.refund_outcome]}{b.refund_inr ? `: ₹${b.refund_inr}` : ""}.</p>}
          {b.refund && (
            <p className="text-sm text-muted">
              {b.refund.status === "confirmed"
                ? `Received, confirmed ${b.refund.confirmed_at?.ist}.`
                : `₹${b.refund.amount_inr} due from the driver by ${b.refund.due_at.ist}.${b.refund.overdue ? " It's overdue and shows on the driver's record." : ""}`}
            </p>
          )}
        </section>
      )}

      {b.role === "passenger" && ["confirmed", "completed"].includes(b.status) && (
        <TripShareCard bookingCode={b.code} />
      )}

      <section className="card mt-3">
        <dl className="grid grid-cols-3 gap-3 text-sm">
          <div><dt className="text-muted">Code</dt><dd className="font-bold tracking-wide">{b.code}</dd></div>
          <div><dt className="text-muted">Fare</dt><dd className="font-bold tabular-nums">₹{b.fare_inr}</dd></div>
          <div><dt className="text-muted">Advance</dt><dd className="font-bold tabular-nums">₹{b.advance_inr}</dd></div>
        </dl>
        {b.seat_role === "co_driver" && <p className="mt-3 rounded-xl bg-paper p-3 text-sm">Licence is self-attested and has not been independently verified. The same fare and cancellation policy apply in this prototype.</p>}
        {b.note && <p className="mt-3 rounded-xl bg-paper p-3 text-sm">&ldquo;{b.note}&rdquo;</p>}
      </section>

      {["requested", "accepted", "advance_claimed", "confirmed"].includes(b.status) && (
        <section className="card mt-3">
          <h2 className="mb-3 text-base font-bold">If plans change</h2>
          {b.free_cancel_any_time ? (
            <p className="text-base">The driver moved the departure, so you can cancel with a full refund any time before it leaves.</p>
          ) : b.cutoffs && (
            <PolicyTimeline cutoffs={b.cutoffs} advance={b.advance_inr} />
          )}
          <p className="mt-3 text-xs text-muted">Agreed under policy {b.policy.label}. Later changes don&apos;t apply to this booking.</p>
        </section>
      )}
    </div>
  );
}
