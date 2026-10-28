import Link from "next/link";
import type { Ride } from "@/lib/types";
import { Reliability } from "./Reliability";

export function RideCard({ ride }: { ride: Ride }) {
  const full = ride.seats_left === 0;
  return (
    <Link href={`/r/${ride.code}`} className="card block transition hover:border-brand/40">
      <div className="flex items-start justify-between gap-3">
        <div>
          <p className="text-base font-bold">
            {ride.origin} <span className="text-muted">to</span> {ride.destination}
          </p>
          <p className="text-sm text-muted">{ride.departure_at.ist}</p>
        </div>
        <div className="text-right">
          <p className="text-lg font-bold">₹{ride.fare_inr.toLocaleString("en-IN")}</p>
          <p className="text-xs text-muted">per seat</p>
        </div>
      </div>
      <div className="mt-3 flex flex-wrap items-center gap-2 text-sm">
        <span className={`pill ${full ? "bg-warn-wash text-warn" : "bg-brand-wash text-brand"}`}>
          {full ? "Full, waitlist open" : `${ride.seats_left} of ${ride.seats_offered} seats left`}
        </span>
        {ride.women_only && <span className="pill bg-pink-50 text-pink-700">Women only</span>}
        {ride.status === "cancelled" && <span className="pill bg-danger-wash text-danger">Cancelled</span>}
      </div>
      <div className="mt-3 flex items-center justify-between gap-2 border-t border-line pt-3 text-sm">
        <span>
          <span className="font-semibold">{ride.driver.name}</span>
          <span className="text-muted"> · {ride.vehicle.colour} {ride.vehicle.make_model}</span>
        </span>
        <Reliability record={ride.driver.reliability} compact />
      </div>
    </Link>
  );
}
