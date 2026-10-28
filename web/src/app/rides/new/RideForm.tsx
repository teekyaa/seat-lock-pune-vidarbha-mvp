"use client";

import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { call, istInputToIso, rupees } from "@/lib/client";
import type { CityPair, FareQuote, Policy, Ride, Vehicle } from "@/lib/types";

export function RideForm({ pairs, vehicles, policy, womenOnlyEligible }: {
  pairs: CityPair[]; vehicles: Vehicle[]; policy: Policy; womenOnlyEligible: boolean;
}) {
  const router = useRouter();
  const [pairId, setPairId] = useState(pairs[0]?.id ?? 0);
  const [vehicleId, setVehicleId] = useState(vehicles[0]?.id ?? 0);
  const [seats, setSeats] = useState(Math.min(3, vehicles[0]?.passenger_seats ?? 3));
  const [departure, setDeparture] = useState("");
  const [fare, setFare] = useState<number | "">("");
  const [quote, setQuote] = useState<FareQuote | null>(null);
  const [pickup, setPickup] = useState("");
  const [dropoff, setDropoff] = useState("");
  const [pickupDetails, setPickupDetails] = useState("");
  const [notes, setNotes] = useState("");
  const [womenOnly, setWomenOnly] = useState(false);
  const [ack, setAck] = useState(false);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  const vehicle = vehicles.find((v) => v.id === vehicleId);
  const maxSeats = Math.min(7, vehicle?.passenger_seats ?? 7);

  useEffect(() => {
    if (!pairId || !seats) return;
    call<FareQuote>(`/fare-quote?city_pair=${pairId}&seats=${seats}`)
      .then((q) => { setQuote(q); setFare((f) => (f === "" || f > q.max_fare_inr ? q.suggested_fare_inr : f)); })
      .catch(() => setQuote(null));
  }, [pairId, seats]);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError("");
    try {
      const ride = await call<Ride>("/rides", "POST", {
        city_pair: pairId, vehicle: vehicleId, seats_offered: seats, departure_at: istInputToIso(departure),
        fare_inr: fare, pickup_point: pickup, dropoff_point: dropoff, pickup_details: pickupDetails, notes,
        women_only: womenOnly, policy_ack: ack,
      });
      router.push(`/r/${ride.code}?posted=1`);
    } catch (err) {
      setError((err as Error).message);
      setBusy(false);
    }
  }

  const overCap = quote && typeof fare === "number" && fare > quote.max_fare_inr;

  return (
    <form onSubmit={submit} className="space-y-4">
      <div className="card space-y-3">
        <div>
          <label className="label" htmlFor="route">Route</label>
          <select id="route" className="field" value={pairId} onChange={(e) => setPairId(Number(e.target.value))}>
            {pairs.map((p) => <option key={p.id} value={p.id}>{p.origin} to {p.destination}</option>)}
          </select>
        </div>
        <div>
          <label className="label" htmlFor="departure">Departure (IST)</label>
          <input id="departure" type="datetime-local" className="field" value={departure}
            onChange={(e) => setDeparture(e.target.value)} required />
          <p className="hint">At least 6 hours from now. Times are India time.</p>
        </div>
        <div className="grid grid-cols-2 gap-3">
          <div>
            <label className="label" htmlFor="pickup">Pickup point</label>
            <input id="pickup" className="field" value={pickup} onChange={(e) => setPickup(e.target.value)} required placeholder="Shivajinagar" />
          </div>
          <div>
            <label className="label" htmlFor="dropoff">Drop-off point</label>
            <input id="dropoff" className="field" value={dropoff} onChange={(e) => setDropoff(e.target.value)} required placeholder="Sitabuldi" />
          </div>
        </div>
        <div>
          <label className="label" htmlFor="pd">Exact pickup details</label>
          <textarea id="pd" className="field" rows={2} value={pickupDetails} onChange={(e) => setPickupDetails(e.target.value)}
            placeholder="Gate 2, blue i20. Call when you arrive." />
          <p className="hint">Only confirmed passengers see this.</p>
        </div>
      </div>

      <div className="card space-y-3">
        <div className="grid grid-cols-2 gap-3">
          <div>
            <label className="label" htmlFor="car">Car</label>
            <select id="car" className="field" value={vehicleId} onChange={(e) => setVehicleId(Number(e.target.value))}>
              {vehicles.map((v) => <option key={v.id} value={v.id}>{v.colour} {v.make_model}</option>)}
            </select>
          </div>
          <div>
            <label className="label" htmlFor="seats">Seats to offer</label>
            <input id="seats" type="number" min={1} max={maxSeats} className="field" value={seats}
              onChange={(e) => setSeats(Math.max(1, Math.min(maxSeats, Number(e.target.value))))} />
          </div>
        </div>
        {quote && (
          <div className="rounded-xl bg-brand-wash p-3 text-sm">
            <p className="font-semibold text-brand">Fair share: {rupees(quote.suggested_fare_inr)} a seat</p>
            <p className="mt-1 text-xs text-muted">
              {quote.distance_km} km at ₹{quote.fuel_cost_per_km}/km plus {rupees(quote.tolls_inr)} tolls, split between
              you and {quote.seats_offered} passenger{quote.seats_offered > 1 ? "s" : ""}. You can ask up to {rupees(quote.max_fare_inr)}.
            </p>
          </div>
        )}
        <div>
          <label className="label" htmlFor="fare">Fare per seat (₹)</label>
          <input id="fare" type="number" min={0} max={quote?.max_fare_inr} className="field" value={fare}
            onChange={(e) => setFare(e.target.value === "" ? "" : Number(e.target.value))} required />
          {overCap && <p className="mt-1 text-xs text-danger">Fares stay cost-sharing. The most you can ask is {rupees(quote!.max_fare_inr)}.</p>}
        </div>
        <div>
          <label className="label" htmlFor="notes">Notes for passengers</label>
          <textarea id="notes" className="field" rows={2} maxLength={500} value={notes} onChange={(e) => setNotes(e.target.value)}
            placeholder="One tea stop near Amravati. Please travel light." />
        </div>
        {womenOnlyEligible && (
          <label className="flex items-center gap-2 text-sm">
            <input type="checkbox" checked={womenOnly} onChange={(e) => setWomenOnly(e.target.checked)} />
            Women-only ride (only verified women can request)
          </label>
        )}
      </div>

      <div className="card space-y-2 text-sm">
        <p className="font-semibold">Cancellation policy ({policy.label})</p>
        <p className="text-muted">{policy.summary}</p>
        <p className="text-muted">
          If you cancel under 48 hours before departure, it shows on your public record. Two late cancellations in one festival
          season pause posting until the season ends.
        </p>
        <label className="flex items-start gap-2 pt-1">
          <input type="checkbox" checked={ack} onChange={(e) => setAck(e.target.checked)} className="mt-1" required />
          <span>I agree to this policy for every passenger on this ride.</span>
        </label>
      </div>

      {error && <p className="text-sm text-danger" role="alert">{error}</p>}
      <button className="btn-primary w-full" disabled={busy || !ack || Boolean(overCap)}>
        {busy ? "Posting" : "Post ride"}
      </button>
    </form>
  );
}
