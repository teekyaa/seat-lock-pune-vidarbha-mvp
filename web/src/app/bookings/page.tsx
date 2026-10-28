import Link from "next/link";
import { redirect } from "next/navigation";
import { ChevronIcon } from "@/components/icons";
import { PageHeader } from "@/components/PageHeader";
import { RouteMark } from "@/components/RouteMark";
import { api, getMe } from "@/lib/server";
import type { Booking, Ride } from "@/lib/types";

export const metadata = { title: "Your trips" };

const LIVE = ["requested", "accepted", "advance_claimed", "confirmed"];
const NEEDS_YOU = (b: Booking) =>
  b.actions.some((a) => ["claim-advance", "accept", "confirm-advance", "refund-received", "trip-confirmation", "dispute-no-show", "no-show"].includes(a) || a.startsWith("reconfirm")) ||
  Boolean(b.refund_pay);

function Row({ href, origin, destination, km, when, sub, badge, urgent }: {
  href: string; origin: string; destination: string; km: number; when: string; sub: string; badge: string; urgent?: boolean;
}) {
  return (
    <Link href={href} className="card flex items-center gap-3 active:bg-paper">
      <RouteMark origin={origin} destination={destination} km={km} size="sm" />
      <span className="min-w-0 flex-1">
        <span className="block truncate font-bold">{origin} to {destination}</span>
        <span className="block text-sm text-muted">{when}</span>
        <span className="block truncate text-sm text-muted">{sub}</span>
        <span className={`pill mt-1.5 ${urgent ? "bg-mile text-ink" : "bg-paper text-muted"}`}>{badge}</span>
      </span>
      <ChevronIcon className="h-5 w-5 shrink-0 text-muted" />
    </Link>
  );
}

export default async function TripsPage() {
  const me = await getMe();
  if (!me) redirect("/login?next=/bookings");
  const [bookings, rides] = await Promise.all([api<Booking[]>("/me/bookings"), api<Ride[]>("/me/rides")]);
  const mine = bookings.filter((b) => b.role === "passenger");
  const asDriver = bookings.filter((b) => b.role === "driver");
  const upcoming = mine.filter((b) => LIVE.includes(b.status));
  const earlier = mine.filter((b) => !LIVE.includes(b.status));
  const driving = rides.filter((r) => r.status === "open");
  const pastRides = rides.filter((r) => r.status !== "open");

  return (
    <div className="pad-tabbar space-y-6">
      <PageHeader title="Your trips" />

      {driving.length > 0 && (
        <section className="space-y-2">
          <h2 className="text-lg font-bold">Driving</h2>
          {driving.map((r) => {
            const pending = asDriver.filter((b) => b.ride_code === r.code && NEEDS_YOU(b)).length;
            return (
              <Row key={r.code} href={`/r/${r.code}`} origin={r.origin} destination={r.destination} km={r.distance_km}
                when={r.departure_at.ist} sub={`${r.seats_offered - r.seats_left} of ${r.seats_offered} seats taken`}
                badge={pending ? `${pending} need${pending > 1 ? "" : "s"} you` : "On track"} urgent={pending > 0} />
            );
          })}
        </section>
      )}

      <section className="space-y-2">
        <h2 className="text-lg font-bold">Booked seats</h2>
        {upcoming.length === 0 ? (
          <div className="card space-y-3 text-center">
            <p className="text-base">No upcoming seats.</p>
            <Link href="/" className="btn-primary w-full">Find a ride</Link>
          </div>
        ) : (
          upcoming.map((b) => (
            <Row key={b.code} href={`/bookings/${b.code}`} origin={b.ride.origin} destination={b.ride.destination} km={b.ride.distance_km}
              when={b.ride.departure_at.ist} sub={`with ${b.ride.driver.name}`}
              badge={NEEDS_YOU(b) ? "Needs you" : b.status === "confirmed" ? "Locked" : b.status_label} urgent={NEEDS_YOU(b)} />
          ))
        )}
      </section>

      {(earlier.length > 0 || pastRides.length > 0) && (
        <details className="group">
          <summary className="flex min-h-12 cursor-pointer list-none items-center justify-between text-lg font-bold">
            Past and cancelled ({earlier.length + pastRides.length})
            <ChevronIcon className="h-5 w-5 rotate-90 text-muted transition-transform group-open:-rotate-90" />
          </summary>
          <div className="space-y-2">
            {pastRides.map((r) => (
              <Row key={r.code} href={`/r/${r.code}`} origin={r.origin} destination={r.destination} km={r.distance_km}
                when={r.departure_at.ist} sub="You drove" badge={r.status === "cancelled" ? "Cancelled" : "Departed"} />
            ))}
            {earlier.map((b) => (
              <Row key={b.code} href={`/bookings/${b.code}`} origin={b.ride.origin} destination={b.ride.destination} km={b.ride.distance_km}
                when={b.ride.departure_at.ist} sub={`with ${b.ride.driver.name}`} badge={NEEDS_YOU(b) ? "Needs you" : b.status_label} urgent={NEEDS_YOU(b)} />
            ))}
          </div>
        </details>
      )}
    </div>
  );
}
