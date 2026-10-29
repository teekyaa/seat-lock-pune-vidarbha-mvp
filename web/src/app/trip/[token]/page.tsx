import type { Metadata } from "next";
import { notFound } from "next/navigation";
import { RouteMark } from "@/components/RouteMark";
import { TopBar } from "@/components/TopBar";
import { ApiError, api } from "@/lib/server";
import type { TripShareDetails } from "@/lib/types";

export const dynamic = "force-dynamic";
export const metadata: Metadata = {
  title: "Shared trip details",
  robots: { index: false, follow: false },
};

export default async function SharedTripPage({ params }: { params: Promise<{ token: string }> }) {
  const { token } = await params;
  let trip: TripShareDetails;
  try {
    trip = await api<TripShareDetails>(`/trip-shares/${encodeURIComponent(token)}`);
  } catch (error) {
    if (error instanceof ApiError && error.status === 404) notFound();
    throw error;
  }

  return (
    <main className="pad-tabbar">
      <TopBar title="Shared trip" />
      <div className="mb-4 rounded-2xl bg-brand-wash p-4">
        <p className="text-base font-bold text-brand">Trip shared with you</p>
        <p className="mt-1 text-sm text-ink">This private link expires {trip.expires_at.ist}. Ask the person who sent it if you need more information.</p>
      </div>

      <section className="flex items-center gap-4">
        <RouteMark origin={trip.origin} destination={trip.destination} size="lg" />
        <div className="min-w-0">
          <p className="text-sm text-muted">{trip.departure_at.ist}</p>
          <h1 className="text-2xl font-extrabold leading-tight">{trip.origin} to {trip.destination}</h1>
          <p className="mt-1 text-sm text-muted">Driver: <span className="font-semibold text-ink">{trip.driver_name}</span></p>
        </div>
      </section>

      <section className="card mt-4">
        <h2 className="text-base font-bold">Car</h2>
        <p className="mt-1 text-lg font-semibold">{trip.vehicle.colour} {trip.vehicle.make_model}</p>
        <p className="text-sm text-muted">Registration: <span className="font-semibold text-ink">{trip.vehicle.registration}</span></p>
      </section>

      <section className="card mt-3">
        <h2 className="text-base font-bold">Route and timing</h2>
        <dl className="mt-3 space-y-3 text-sm">
          <div><dt className="text-muted">Pickup</dt><dd className="font-semibold">{trip.pickup_point}, {trip.origin}</dd></div>
          <div><dt className="text-muted">Drop-off</dt><dd className="font-semibold">{trip.dropoff_point}, {trip.destination}</dd></div>
          <div><dt className="text-muted">Expected arrival</dt><dd className="font-semibold">{trip.expected_arrival_at.ist}</dd></div>
        </dl>
      </section>

      <p className="mt-4 rounded-xl bg-paper p-3 text-xs text-muted">
        This link only shows trip details. It does not provide live location tracking or emergency services. Anyone with the link can view it until it expires or the passenger turns it off.
      </p>
    </main>
  );
}
