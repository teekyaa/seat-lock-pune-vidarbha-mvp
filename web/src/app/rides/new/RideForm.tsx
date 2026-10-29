"use client";

import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { ActionBar } from "@/components/ActionBar";
import { RouteMark } from "@/components/RouteMark";
import { call, istInputToIso, rupees } from "@/lib/client";
import type { CityPair, FareQuote, Policy, Ride, Vehicle } from "@/lib/types";

const STEPS = ["Route", "Seats and fare", "Pickup", "Review"];

/** Earliest allowed departure (6 h ahead), as a datetime-local value in IST. */
function minDeparture() {
  const d = new Date(Date.now() + 6 * 3600_000 + 5.5 * 3600_000);
  return d.toISOString().slice(0, 16);
}

function istLabel(value: string) {
  if (!value) return "";
  return new Intl.DateTimeFormat("en-IN", {
    timeZone: "Asia/Kolkata", weekday: "short", day: "numeric", month: "short", hour: "numeric", minute: "2-digit",
  }).format(new Date(istInputToIso(value))) + " IST";
}

export function RideForm({ pairs: allPairs, vehicles, policy, womenOnlyEligible }: {
  pairs: CityPair[]; vehicles: Vehicle[]; policy: Policy; womenOnlyEligible: boolean;
}) {
  // Most drivers head home from Pune, so those routes come first.
  const pairs = [...allPairs].sort((a, b) => Number(b.origin === "Pune") - Number(a.origin === "Pune"));
  const router = useRouter();
  const [step, setStep] = useState(0);
  const [pairId, setPairId] = useState(pairs[0]?.id ?? 0);
  const [vehicleId, setVehicleId] = useState(vehicles[0]?.id ?? 0);
  const vehicle = vehicles.find((v) => v.id === vehicleId);
  const maxSeats = Math.min(7, vehicle?.passenger_seats ?? 7);
  const [seats, setSeats] = useState(Math.min(3, maxSeats));
  const [departure, setDeparture] = useState("");
  const [fare, setFare] = useState<number | "">("");
  const [quote, setQuote] = useState<FareQuote | null>(null);
  const [pickup, setPickup] = useState("");
  const [dropoff, setDropoff] = useState("");
  const [pickupDetails, setPickupDetails] = useState("");
  const [notes, setNotes] = useState("");
  const [womenOnly, setWomenOnly] = useState(false);
  const [codriverWanted, setCodriverWanted] = useState(false);
  const [ack, setAck] = useState(false);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const pair = pairs.find((p) => p.id === pairId);

  useEffect(() => {
    if (!pairId || !seats) return;
    call<FareQuote>(`/fare-quote?city_pair=${pairId}&seats=${seats}`)
      .then((q) => { setQuote(q); setFare((f) => (f === "" || f > q.max_fare_inr ? q.suggested_fare_inr : f)); })
      .catch(() => setQuote(null));
  }, [pairId, seats]);

  const overCap = Boolean(quote && typeof fare === "number" && fare > quote.max_fare_inr);
  const valid = [
    Boolean(pairId && departure),
    Boolean(vehicleId && seats && fare !== "" && !overCap),
    Boolean(pickup.trim() && dropoff.trim()),
    ack,
  ];

  async function submit() {
    setBusy(true);
    setError("");
    try {
      const ride = await call<Ride>("/rides", "POST", {
        city_pair: pairId, vehicle: vehicleId, seats_offered: seats, departure_at: istInputToIso(departure),
        fare_inr: fare, pickup_point: pickup, dropoff_point: dropoff, pickup_details: pickupDetails, notes,
        women_only: womenOnly, codriver_wanted: codriverWanted, policy_ack: ack,
      });
      router.push(`/r/${ride.code}?posted=1`);
    } catch (err) {
      setError((err as Error).message);
      setBusy(false);
    }
  }

  return (
    <div className="pad-actionbar">
      <ol className="mb-5 grid grid-cols-4 gap-1.5" aria-label="Steps">
        {STEPS.map((s, i) => (
          <li key={s} aria-current={i === step ? "step" : undefined}>
            <span className={`block h-1.5 rounded-full ${i <= step ? "bg-brand" : "bg-line"}`} />
            <span className={`mt-1.5 block text-[11px] font-semibold ${i === step ? "text-ink" : "text-muted"}`}>{s}</span>
          </li>
        ))}
      </ol>

      {step === 0 && (
        <div className="space-y-5">
          <fieldset>
            <legend className="label">Where are you driving?</legend>
            <div className="grid gap-2">
              {pairs.map((p) => (
                <label key={p.id} className={`flex min-h-14 items-center justify-between rounded-xl bg-surface px-4 ring-1 ${pairId === p.id ? "ring-2 ring-brand" : "ring-line"}`}>
                  <span className="flex items-center gap-3">
                    <input type="radio" name="route" checked={pairId === p.id} onChange={() => setPairId(p.id)} className="h-5 w-5 accent-brand" />
                    <span className="font-semibold">{p.origin} to {p.destination}</span>
                  </span>
                  <span className="text-sm text-muted tabular-nums">{p.distance_km} km</span>
                </label>
              ))}
            </div>
          </fieldset>
          <div>
            <label className="label" htmlFor="departure">Leaving at (India time)</label>
            <input id="departure" type="datetime-local" className="field" min={minDeparture()} value={departure}
              onChange={(e) => setDeparture(e.target.value)} required />
            <p className="hint">{departure ? istLabel(departure) : "At least 6 hours from now."}</p>
          </div>
        </div>
      )}

      {step === 1 && (
        <div className="space-y-5">
          {vehicles.length > 1 && (
            <div>
              <label className="label" htmlFor="car">Car</label>
              <select id="car" className="field" value={vehicleId} onChange={(e) => setVehicleId(Number(e.target.value))}>
                {vehicles.map((v) => <option key={v.id} value={v.id}>{v.colour} {v.make_model}</option>)}
              </select>
            </div>
          )}
          <div>
            <span className="label">Seats to offer</span>
            <div className="flex items-center justify-between rounded-xl bg-surface p-2 ring-1 ring-line">
              <button type="button" aria-label="Fewer seats" className="btn-secondary h-12 w-12 px-0 text-2xl" disabled={seats <= 1} onClick={() => setSeats(seats - 1)}>−</button>
              <span className="text-2xl font-extrabold tabular-nums" aria-live="polite">{seats}</span>
              <button type="button" aria-label="More seats" className="btn-secondary h-12 w-12 px-0 text-2xl" disabled={seats >= maxSeats} onClick={() => setSeats(seats + 1)}>+</button>
            </div>
            <p className="hint">Your {vehicle?.make_model} takes up to {maxSeats}.</p>
          </div>
          {quote && (
            <div className="rounded-2xl bg-brand-wash p-4">
              <p className="text-sm text-brand">Fair share for each person</p>
              <p className="text-3xl font-extrabold tabular-nums text-brand">{rupees(quote.suggested_fare_inr)}</p>
              <p className="mt-1 text-sm text-muted">
                {quote.distance_km} km at ₹{quote.fuel_cost_per_km}/km plus {rupees(quote.tolls_inr)} tolls, split {quote.seats_offered + 1} ways including you.
              </p>
            </div>
          )}
          <div>
            <label className="label" htmlFor="fare">Your fare per seat</label>
            <div className="relative">
              <span className="pointer-events-none absolute left-3.5 top-1/2 -translate-y-1/2 text-base font-semibold text-muted">₹</span>
              <input id="fare" type="number" inputMode="numeric" min={0} max={quote?.max_fare_inr} className="field pl-8 text-lg font-bold tabular-nums"
                value={fare} onChange={(e) => setFare(e.target.value === "" ? "" : Number(e.target.value))} />
            </div>
            <p className={`hint ${overCap ? "text-danger" : ""}`}>
              {overCap ? `Fares stay cost-sharing. The most you can ask is ${rupees(quote!.max_fare_inr)}.` : quote ? `Up to ${rupees(quote.max_fare_inr)}.` : ""}
            </p>
          </div>
        </div>
      )}

      {step === 2 && (
        <div className="space-y-5">
          <div>
            <label className="label" htmlFor="pickup">Pickup in {pair?.origin}</label>
            <input id="pickup" className="field" value={pickup} onChange={(e) => setPickup(e.target.value)} placeholder="Shivajinagar bus stand" autoComplete="off" />
          </div>
          <div>
            <label className="label" htmlFor="dropoff">Drop-off in {pair?.destination}</label>
            <input id="dropoff" className="field" value={dropoff} onChange={(e) => setDropoff(e.target.value)} placeholder="Sitabuldi" autoComplete="off" />
          </div>
          <div>
            <label className="label" htmlFor="pd">Exact meeting spot</label>
            <textarea id="pd" className="field" rows={2} value={pickupDetails} onChange={(e) => setPickupDetails(e.target.value)} placeholder="Gate 2, blue i20. Call when you arrive." />
            <p className="hint">Only confirmed passengers see this.</p>
          </div>
          <div>
            <label className="label" htmlFor="notes">Anything passengers should know?</label>
            <textarea id="notes" className="field" rows={2} maxLength={500} value={notes} onChange={(e) => setNotes(e.target.value)} placeholder="One tea stop near Amravati. Please travel light." />
          </div>
          <label className="flex min-h-12 items-center gap-3 rounded-xl bg-surface px-4 ring-1 ring-line">
            <input type="checkbox" checked={codriverWanted} onChange={(e) => setCodriverWanted(e.target.checked)} className="h-5 w-5 accent-brand" />
            I am looking for a co-driver
          </label>
          {codriverWanted && <p className="rounded-xl bg-paper p-3 text-sm text-muted">Co-drivers book a seat and share driving. The same listed fare and cancellation policy apply in this prototype. Licence status is self-attested, not verified.</p>}
          {womenOnlyEligible && (
            <label className="flex min-h-12 items-center gap-3 rounded-xl bg-surface px-4 ring-1 ring-line">
              <input type="checkbox" checked={womenOnly} onChange={(e) => setWomenOnly(e.target.checked)} className="h-5 w-5 accent-brand" />
              Women only (verified members can request)
            </label>
          )}
        </div>
      )}

      {step === 3 && pair && (
        <div className="space-y-4">
          <div className="card flex items-center gap-4">
            <RouteMark origin={pair.origin} destination={pair.destination} km={pair.distance_km} />
            <div>
              <p className="text-lg font-extrabold">{pair.origin} to {pair.destination}</p>
              <p className="text-sm text-muted">{istLabel(departure)}</p>
              <p className="text-sm text-muted">{seats} seat{seats > 1 ? "s" : ""} at {typeof fare === "number" ? rupees(fare) : ""}, from {pickup}</p>
              {codriverWanted && <p className="mt-1 text-sm font-semibold text-brand">Co-driver welcome · same fare</p>}
            </div>
          </div>
          <div className="card space-y-3 text-sm">
            <p className="text-base font-bold">What you&apos;re agreeing to</p>
            <p>{policy.summary}</p>
            <p>If you cancel less than 48 hours before departure, it shows on your public record. Two late cancellations in one festival season pause your posting until the season ends.</p>
          </div>
          <label className="flex min-h-12 items-start gap-3 text-base">
            <input type="checkbox" checked={ack} onChange={(e) => setAck(e.target.checked)} className="mt-1 h-5 w-5 accent-brand" />
            <span>I agree to this policy for every passenger on this ride.</span>
          </label>
        </div>
      )}

      {error && <p className="mt-4 rounded-xl bg-danger-wash p-3 text-sm text-danger" role="alert">{error}</p>}

      <ActionBar>
        <div className="grid grid-cols-[auto_1fr] gap-2">
          <button type="button" className="btn-secondary" disabled={step === 0} onClick={() => setStep(step - 1)}>Back</button>
          {step < 3 ? (
            <button type="button" className="btn-primary" disabled={!valid[step]} onClick={() => { setError(""); setStep(step + 1); }}>Next</button>
          ) : (
            <button type="button" className="btn-primary" disabled={busy || !valid.every(Boolean)} onClick={submit}>{busy ? "Posting" : "Post ride"}</button>
          )}
        </div>
      </ActionBar>
    </div>
  );
}
