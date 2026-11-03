import Link from "next/link";
import type { Ride } from "@/lib/types";
import { RouteMark } from "./RouteMark";

function timeOf(ist: string) {
  // "Sat 7 Nov, 9:00 pm IST" -> ["Sat 7 Nov", "9:00 pm"]
  const [day, rest = ""] = ist.split(", ");
  return [day, rest.replace(" IST", "")];
}

/** Routes differ near the end, so a card shows the last stops: "via … Jalna and Wardha". */
function shortVia(names: string[]) {
  const middle = names.slice(1, -1);
  if (!middle.length) return "Direct";
  if (middle.length <= 2) return `via ${middle.join(" and ")}`;
  return `via … ${middle.slice(-2).join(" and ")}`;
}

export function RideCard({ ride }: { ride: Ride }) {
  const full = ride.seats_left === 0;
  const [day, time] = timeOf(ride.departure_at.ist);
  const r = ride.driver.reliability;
  const late = r.driver_late_cancellations;
  return (
    <Link href={`/r/${ride.code}`} className="card flex gap-3.5 active:bg-paper">
      <RouteMark origin={ride.origin} destination={ride.destination} km={ride.distance_km} size="sm" />
      <div className="min-w-0 flex-1">
        <div className="flex items-baseline justify-between gap-2">
          <p className="text-lg font-extrabold leading-tight">{time}</p>
          <p className="text-lg font-extrabold leading-tight tabular-nums">₹{ride.fare_inr.toLocaleString("en-IN")}</p>
        </div>
        <p className="text-sm text-muted">{day}, from {ride.pickup_point}</p>
        {ride.route && <p className="truncate text-sm text-muted">{shortVia(ride.route.stops.map((s) => s.name))}</p>}
        <div className="mt-2 flex flex-wrap items-center gap-1.5">
          <span className={`pill ${full ? "bg-warn-wash text-warn" : "bg-brand-wash text-brand"}`}>
            {full ? "Full, join waitlist" : `${ride.seats_left} seat${ride.seats_left > 1 ? "s" : ""} left`}
          </span>
          {ride.women_only && <span className="pill bg-pink-50 text-pink-800">Women only</span>}
          {ride.codriver_wanted && <span className="pill bg-mile-wash text-brand">Co-driver wanted</span>}
          {!ride.advance_required && <span className="pill bg-paper text-muted ring-1 ring-line">No advance</span>}
          {ride.status === "cancelled" && <span className="pill bg-danger-wash text-danger">Cancelled</span>}
        </div>
        <p className="mt-2 truncate text-sm">
          <span className="font-semibold">{ride.driver.name}</span>
          <span className="text-muted">
            , {r.completed_trips} trip{r.completed_trips === 1 ? "" : "s"}
            {late > 0 && `, ${late} late cancel${late > 1 ? "s" : ""}`}
          </span>
        </p>
      </div>
    </Link>
  );
}
