import Link from "next/link";
import { redirect } from "next/navigation";
import { api, getMe } from "@/lib/server";
import type { Booking, Ride } from "@/lib/types";

export const metadata = { title: "Your trips" };

const LIVE = ["requested", "accepted", "advance_claimed", "confirmed"];

export default async function BookingsPage() {
  const me = await getMe();
  if (!me) redirect("/login?next=/bookings");
  const [bookings, rides] = await Promise.all([api<Booking[]>("/me/bookings"), api<Ride[]>("/me/rides")]);
  const mine = bookings.filter((b) => b.role === "passenger");
  const upcoming = mine.filter((b) => LIVE.includes(b.status));
  const earlier = mine.filter((b) => !LIVE.includes(b.status));

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold">Your trips</h1>

      {rides.length > 0 && (
        <section className="space-y-2">
          <h2 className="text-sm font-semibold uppercase tracking-wide text-muted">Rides you&apos;re driving</h2>
          {rides.map((r) => (
            <Link key={r.code} href={`/r/${r.code}`} className="card flex items-center justify-between">
              <span>
                <span className="block font-semibold">{r.origin} to {r.destination}</span>
                <span className="text-sm text-muted">{r.departure_at.ist}</span>
              </span>
              <span className="pill bg-paper">{r.status === "open" ? `${r.seats_offered - r.seats_left}/${r.seats_offered} taken` : r.status}</span>
            </Link>
          ))}
        </section>
      )}

      <section className="space-y-2">
        <h2 className="text-sm font-semibold uppercase tracking-wide text-muted">Seats you&apos;ve booked</h2>
        {upcoming.length === 0 && <p className="card text-sm text-muted">Nothing booked yet. <Link href="/" className="text-brand underline">Find a ride</Link>.</p>}
        {upcoming.map((b) => <BookingRow key={b.code} b={b} />)}
      </section>

      {earlier.length > 0 && (
        <section className="space-y-2">
          <h2 className="text-sm font-semibold uppercase tracking-wide text-muted">Earlier</h2>
          {earlier.map((b) => <BookingRow key={b.code} b={b} />)}
        </section>
      )}
    </div>
  );
}

function BookingRow({ b }: { b: Booking }) {
  const needsYou = b.actions.some((a) => ["claim-advance", "refund-received", "trip-confirmation", "dispute-no-show"].includes(a) || a.startsWith("reconfirm"));
  return (
    <Link href={`/bookings/${b.code}`} className="card flex items-center justify-between gap-3">
      <span>
        <span className="block font-semibold">{b.ride.origin} to {b.ride.destination}</span>
        <span className="text-sm text-muted">{b.ride.departure_at.ist} · {b.code}</span>
      </span>
      <span className={`pill ${needsYou ? "bg-warn-wash text-warn" : "bg-paper"}`}>{needsYou ? "Action needed" : b.status_label}</span>
    </Link>
  );
}
