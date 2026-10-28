import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";
import { Reliability } from "@/components/Reliability";
import { ApiError, api, getMe } from "@/lib/server";
import type { Booking, Ride } from "@/lib/types";
import { DriverPanel } from "./DriverPanel";
import { RideActions } from "./RideActions";
import { ShareButtons } from "./ShareButtons";

type Props = { params: Promise<{ code: string }>; searchParams: Promise<{ posted?: string }> };

async function load(code: string) {
  try {
    return await api<Ride>(`/rides/${encodeURIComponent(code)}`);
  } catch (e) {
    if (e instanceof ApiError && e.status === 404) notFound();
    throw e;
  }
}

export async function generateMetadata({ params }: Props): Promise<Metadata> {
  const { code } = await params;
  const ride = await load(code);
  const title = `${ride.origin} to ${ride.destination}, ${ride.departure_at.ist}`;
  const description = `₹${ride.fare_inr} a seat · ${ride.seats_left} of ${ride.seats_offered} seats left · driven by ${ride.driver.name}`;
  return { title, description, openGraph: { title, description, type: "website" } };
}

export default async function RidePage({ params, searchParams }: Props) {
  const { code } = await params;
  const { posted } = await searchParams;
  const [ride, me] = await Promise.all([load(code), getMe()]);
  const isDriver = Boolean(ride.viewer?.is_driver);
  const driverData = isDriver
    ? await api<{ bookings: Booking[]; waitlist: { id: number; passenger: string; status: string }[] }>(`/rides/${ride.code}/bookings`)
    : null;
  const shareUrl = `${process.env.NEXT_PUBLIC_SITE_URL ?? "http://localhost:3000"}/r/${ride.code}`;

  return (
    <div className="space-y-4">
      {posted && (
        <p className="rounded-xl bg-brand-wash p-3 text-sm text-brand">Your ride is live. Share it in your WhatsApp group so people can book.</p>
      )}
      <section className="card space-y-3">
        <div className="flex items-start justify-between gap-3">
          <div>
            <h1 className="text-xl font-bold">{ride.origin} to {ride.destination}</h1>
            <p className="text-sm text-muted">Leaves {ride.departure_at.ist}</p>
            <p className="text-sm text-muted">Arrives around {ride.expected_arrival_at.ist}</p>
          </div>
          <div className="text-right">
            <p className="text-2xl font-bold">₹{ride.fare_inr.toLocaleString("en-IN")}</p>
            <p className="text-xs text-muted">per seat</p>
          </div>
        </div>
        <div className="flex flex-wrap gap-2 text-sm">
          {ride.status === "cancelled" ? (
            <span className="pill bg-danger-wash text-danger">Cancelled by the driver</span>
          ) : (
            <span className="pill bg-brand-wash text-brand">{ride.seats_left} of {ride.seats_offered} seats left</span>
          )}
          {ride.women_only && <span className="pill bg-pink-50 text-pink-700">Women only, verified members</span>}
          <span className="pill bg-paper text-muted">Fair share ₹{ride.suggested_fare_inr}</span>
        </div>
        <dl className="grid grid-cols-2 gap-3 text-sm">
          <div><dt className="text-muted">Pickup</dt><dd className="font-medium">{ride.pickup_point}</dd></div>
          <div><dt className="text-muted">Drop-off</dt><dd className="font-medium">{ride.dropoff_point}</dd></div>
          <div><dt className="text-muted">Car</dt><dd className="font-medium">{ride.vehicle.colour} {ride.vehicle.make_model}</dd></div>
          <div><dt className="text-muted">Advance to lock a seat</dt><dd className="font-medium">₹{ride.advance_inr} over UPI</dd></div>
        </dl>
        {ride.notes && <p className="rounded-xl bg-paper p-3 text-sm">{ride.notes}</p>}
        {ride.private && (
          <div className="rounded-xl border border-brand/30 bg-brand-wash p-3 text-sm">
            <p className="font-semibold text-brand">For confirmed travellers</p>
            <p>Driver: <a href={`tel:${ride.private.driver_phone}`} className="font-semibold underline">{ride.private.driver_phone}</a></p>
            <p>Registration: {ride.private.registration}</p>
            {ride.private.pickup_details && <p>Pickup: {ride.private.pickup_details}</p>}
          </div>
        )}
        <ShareButtons url={shareUrl} text={`Seat Lock ride: ${ride.origin} to ${ride.destination}, ${ride.departure_at.ist}. ₹${ride.fare_inr} a seat, ${ride.seats_left} left.`} />
      </section>

      <section className="card space-y-3">
        <Link href={`/u/${ride.driver.id}`} className="flex items-center justify-between">
          <span>
            <span className="block font-semibold">{ride.driver.name}</span>
            <span className="text-sm text-muted">From {ride.driver.hometown} · on Seat Lock since {ride.driver.member_since.slice(0, 4)}</span>
          </span>
          <span className="text-sm font-semibold text-brand">Record</span>
        </Link>
        <Reliability record={ride.driver.reliability} compact />
      </section>

      {isDriver && driverData ? (
        <DriverPanel ride={ride} bookings={driverData.bookings} waitlist={driverData.waitlist} />
      ) : (
        <RideActions ride={ride} signedIn={Boolean(me)} profileComplete={Boolean(me?.profile_complete)} />
      )}

      {ride.policy && ride.cutoffs && (
        <section className="card space-y-2 text-sm">
          <h2 className="font-bold">If plans change</h2>
          <ul className="space-y-1">
            <li>Cancel before <b>{ride.cutoffs.full_refund_until.ist}</b>: full advance back.</li>
            <li>From then until <b>{ride.cutoffs.full_penalty_from.ist}</b>: the driver keeps half.</li>
            <li>After that, or if you don&apos;t turn up: the driver keeps it all.</li>
            <li>If your seat is refilled, or the driver cancels: full advance back.</li>
          </ul>
          <p className="text-xs text-muted">Policy {ride.policy.label}. These times are fixed for this ride and won&apos;t change later.</p>
        </section>
      )}
    </div>
  );
}
