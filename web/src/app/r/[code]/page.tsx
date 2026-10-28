import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";
import { ChevronIcon, PhoneIcon } from "@/components/icons";
import { PolicyTimeline } from "@/components/PolicyTimeline";
import { RouteMark } from "@/components/RouteMark";
import { TopBar } from "@/components/TopBar";
import { ApiError, api, getMe } from "@/lib/server";
import type { Booking, Ride } from "@/lib/types";
import { DriverPanel } from "./DriverPanel";
import { RideActions } from "./RideActions";
import { ShareButton } from "./ShareButtons";

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
  const description = `₹${ride.fare_inr} a seat, ${ride.seats_left} of ${ride.seats_offered} seats left, driven by ${ride.driver.name}`;
  return { title, description, openGraph: { title, description, type: "website" } };
}

function split(ist: string) {
  const [day, rest = ""] = ist.split(", ");
  return { day, time: rest.replace(" IST", "") };
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
  const shareText = `${ride.origin} to ${ride.destination}, ${ride.departure_at.ist}. ₹${ride.fare_inr} a seat, ${ride.seats_left} left. Book on Seat Lock:`;
  const dep = split(ride.departure_at.ist);
  const arr = split(ride.expected_arrival_at.ist);
  const r = ride.driver.reliability;

  return (
    <div className="pad-actionbar">
      <TopBar title={`${ride.origin} to ${ride.destination}`} trailing={<ShareButton url={shareUrl} text={shareText} />} />

      {posted && (
        <div className="mb-4 space-y-3 rounded-2xl bg-mile-wash p-4">
          <p className="text-base font-bold">Your ride is live</p>
          <p className="text-sm">Share it in your WhatsApp group. The link shows the route, time, fare and seats left.</p>
          <ShareButton url={shareUrl} text={shareText} variant="button" />
        </div>
      )}

      <section className="flex items-start gap-4">
        <RouteMark origin={ride.origin} destination={ride.destination} km={ride.distance_km} size="lg" />
        <div className="min-w-0 pt-1">
          <p className="text-sm font-semibold text-muted">{dep.day}</p>
          <p className="text-3xl font-extrabold leading-none tracking-tight">{dep.time}</p>
          <p className="mt-2 text-2xl font-extrabold tabular-nums">
            ₹{ride.fare_inr.toLocaleString("en-IN")}<span className="text-base font-semibold text-muted"> a seat</span>
          </p>
          <div className="mt-2 flex flex-wrap gap-1.5">
            {ride.status === "cancelled" ? (
              <span className="pill bg-danger-wash text-danger">Cancelled by the driver</span>
            ) : (
              <span className={`pill ${ride.seats_left ? "bg-brand-wash text-brand" : "bg-warn-wash text-warn"}`}>
                {ride.seats_left ? `${ride.seats_left} of ${ride.seats_offered} seats left` : "Full, waitlist open"}
              </span>
            )}
            {ride.women_only && <span className="pill bg-pink-50 text-pink-800">Women only</span>}
          </div>
        </div>
      </section>

      <section className="card mt-5" aria-label="Journey">
        <ol className="relative space-y-5 pl-7">
          <span className="absolute bottom-3 left-[7px] top-3 w-0.5 bg-ink/15" aria-hidden />
          <li className="relative">
            <span className="absolute -left-7 top-1 h-4 w-4 rounded-full border-[3px] border-brand bg-surface" aria-hidden />
            <p className="text-sm text-muted">Leaves {dep.time}</p>
            <p className="text-base font-bold">{ride.pickup_point}, {ride.origin}</p>
          </li>
          <li className="relative">
            <span className="absolute -left-7 top-1 h-4 w-4 rounded-full bg-brand" aria-hidden />
            <p className="text-sm text-muted">Arrives around {arr.day === dep.day ? arr.time : `${arr.time}, ${arr.day}`}</p>
            <p className="text-base font-bold">{ride.dropoff_point}, {ride.destination}</p>
          </li>
        </ol>
        <dl className="mt-4 grid grid-cols-2 gap-3 border-t border-line pt-4 text-sm">
          <div><dt className="text-muted">Car</dt><dd className="font-semibold">{ride.vehicle.colour} {ride.vehicle.make_model}</dd></div>
          <div><dt className="text-muted">Advance to lock a seat</dt><dd className="font-semibold">₹{ride.advance_inr} over UPI</dd></div>
        </dl>
        {ride.notes && <p className="mt-4 rounded-xl bg-paper p-3 text-sm">&ldquo;{ride.notes}&rdquo;</p>}
      </section>

      {ride.private && (
        <section className="mt-3 rounded-2xl bg-brand p-4 text-white">
          <p className="text-sm text-white/80">{isDriver ? "Shared with your confirmed passengers" : "You're confirmed on this ride"}</p>
          <p className="mt-1 text-base font-bold">Car {ride.private.registration}</p>
          {ride.private.pickup_details && <p className="mt-1 text-sm">{ride.private.pickup_details}</p>}
          {!isDriver && (
            <a href={`tel:${ride.private.driver_phone}`} className="btn mt-3 w-full bg-white text-brand">
              <PhoneIcon /> Call {ride.driver.name.split(" ")[0]}
            </a>
          )}
        </section>
      )}

      <Link href={`/u/${ride.driver.id}`} className="card mt-3 flex items-center gap-3 active:bg-paper">
        <span className="grid h-12 w-12 shrink-0 place-items-center rounded-full bg-brand-wash text-lg font-extrabold text-brand">
          {ride.driver.name.slice(0, 1)}
        </span>
        <span className="min-w-0 flex-1">
          <span className="block font-bold">{ride.driver.name}</span>
          <span className="block text-sm text-muted">
            From {ride.driver.hometown}. {r.completed_trips} completed trip{r.completed_trips === 1 ? "" : "s"}
            {r.driver_late_cancellations > 0 && `, ${r.driver_late_cancellations} late cancellation${r.driver_late_cancellations > 1 ? "s" : ""}`}
            {r.open_refund_disputes > 0 && `, ${r.open_refund_disputes} refund overdue`}.
          </span>
        </span>
        <ChevronIcon className="h-5 w-5 text-muted" />
      </Link>

      {isDriver && driverData && <DriverPanel ride={ride} bookings={driverData.bookings} waitlist={driverData.waitlist} shareUrl={shareUrl} />}

      {!isDriver && ride.cutoffs && (
        <section className="card mt-3">
          <h2 className="mb-3 text-lg font-bold">If plans change</h2>
          <PolicyTimeline cutoffs={ride.cutoffs} advance={ride.advance_inr} />
          <p className="mt-3 text-xs text-muted">Policy {ride.policy?.label}. These times are fixed for this ride.</p>
        </section>
      )}

      {!isDriver && (
        <RideActions ride={ride} signedIn={Boolean(me)} profileComplete={Boolean(me?.profile_complete)} />
      )}
    </div>
  );
}
