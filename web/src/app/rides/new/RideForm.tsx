"use client";

import { useRouter } from "next/navigation";
import { useEffect, useMemo, useState } from "react";
import { ActionBar } from "@/components/ActionBar";
import { PickupSearch } from "@/components/PickupSearch";
import { PlacePicker } from "@/components/PlacePicker";
import { RouteDiagram } from "@/components/RouteDiagram";
import { call, istInputToIso, rupees } from "@/lib/client";
import type { PickupResult, Place, Policy, Ride, RouteOption, RouteQuote, Vehicle } from "@/lib/types";

const STEPS = ["Route", "Stops and pickup", "Seats and fare", "Review"];

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

function hoursLabel(minutes: number | null) {
  if (!minutes) return "";
  const h = Math.floor(minutes / 60);
  const m = minutes % 60;
  return m ? `about ${h} h ${m} min` : `about ${h} h`;
}

/** Lead each route card with the stops that set it apart, e.g. "via Yavatmal and Wani". */
function distinctLabel(option: RouteOption, all: RouteOption[]) {
  const middle = (o: RouteOption) => o.stops.slice(1, -1).map((s) => s.name);
  if (all.length < 2) return option.label;
  const shared = middle(all[0]).filter((n) => all.every((o) => middle(o).includes(n)));
  const own = middle(option).filter((n) => !shared.includes(n));
  if (!own.length) return option.label;
  return "via " + (own.length === 1 ? own[0] : `${own.slice(0, -1).join(", ")} and ${own[own.length - 1]}`);
}

/** Same rounding as the API: percentage of the fare to the nearest ₹50, at least ₹50, never above the fare. */
function advanceFor(fare: number, percent: number) {
  if (fare <= 0) return 0;
  const rounded = Math.floor((fare * percent) / 100 / 50 + 0.5) * 50;
  return Math.min(fare, rounded || 50);
}

export function RideForm({ places, vehicles, policy, womenOnlyEligible, hasUpi }: {
  places: Place[]; vehicles: Vehicle[]; policy: Policy; womenOnlyEligible: boolean; hasUpi: boolean;
}) {
  const router = useRouter();
  const [step, setStep] = useState(0);
  const [from, setFrom] = useState<Place | null>(() => places.find((p) => p.name === "Pune") ?? null);
  const [to, setTo] = useState<Place | null>(null);
  const [options, setOptions] = useState<RouteOption[] | null>(null);
  const [routeId, setRouteId] = useState<number | null>(null);
  const [departure, setDeparture] = useState("");
  const [disabled, setDisabled] = useState<Set<number>>(new Set());
  const [pickup, setPickup] = useState<PickupResult>({ name: "", address: "", eloc: "" });
  const [dropoff, setDropoff] = useState("");
  const [pickupDetails, setPickupDetails] = useState("");
  const [notes, setNotes] = useState("");
  const [vehicleId, setVehicleId] = useState(vehicles[0]?.id ?? 0);
  const vehicle = vehicles.find((v) => v.id === vehicleId);
  const maxSeats = Math.min(7, vehicle?.passenger_seats ?? 7);
  const [seats, setSeats] = useState(Math.min(3, maxSeats));
  const [quote, setQuote] = useState<RouteQuote | null>(null);
  const [fare, setFare] = useState<number | "">("");
  // The fare follows the fair share until the driver types their own.
  const [fareTouched, setFareTouched] = useState(false);
  const [advanceRequired, setAdvanceRequired] = useState(hasUpi);
  const [womenOnly, setWomenOnly] = useState(false);
  const [codriverWanted, setCodriverWanted] = useState(false);
  const [ack, setAck] = useState(false);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  const route = options?.find((o) => o.id === routeId) ?? null;
  const stops = useMemo(
    () => (route?.stops ?? []).map((s) => ({ ...s, enabled: !disabled.has(s.place_id) })),
    [route, disabled],
  );

  // Via-route options for From and To.
  useEffect(() => {
    setOptions(null);
    setRouteId(null);
    setDisabled(new Set());
    setFareTouched(false);
    if (!from || !to) return;
    let live = true;
    call<RouteOption[]>(`/routes?from=${from.id}&to=${to.id}`)
      .then((list) => {
        if (!live) return;
        setOptions(list);
        setRouteId(list.find((o) => o.ready)?.id ?? null);
      })
      .catch((e) => live && setError((e as Error).message));
    return () => { live = false; };
  }, [from, to]);

  // Cost share and cap for this route and seat count.
  useEffect(() => {
    setQuote(null);
    if (!route || !from || !to || !route.ready) return;
    let live = true;
    call<RouteQuote>(`/route-quote?route=${route.id}&from=${from.id}&to=${to.id}&seats=${seats}`)
      .then((q) => {
        if (!live) return;
        setQuote(q);
        setFare((f) => (!fareTouched || f === "" || f > q.max_fare_inr ? q.suggested_fare_inr : f));
      })
      .catch(() => live && setQuote(null));
    return () => { live = false; };
  }, [route, from, to, seats, fareTouched]);

  const fareOk = typeof fare === "number" && Number.isInteger(fare) && fare >= 0;
  const overCap = Boolean(quote && fareOk && (fare as number) > quote.max_fare_inr);
  const advance = advanceRequired && fareOk ? advanceFor(fare as number, policy.advance_percent) : 0;
  const valid = [
    Boolean(from && to && route?.ready && departure),
    Boolean(pickup.name.trim() && dropoff.trim()),
    Boolean(vehicleId && seats && quote && fareOk && !overCap),
    ack,
  ];

  async function submit() {
    if (!from || !to || !route) return;
    setBusy(true);
    setError("");
    try {
      const ride = await call<Ride>("/rides", "POST", {
        route: route.id, from_place: from.id, to_place: to.id, vehicle: vehicleId, seats_offered: seats,
        departure_at: istInputToIso(departure), fare_inr: fare, pickup, dropoff_point: dropoff,
        disabled_stops: [...disabled], pickup_details: pickupDetails, notes, women_only: womenOnly,
        codriver_wanted: codriverWanted, advance_required: advanceRequired, policy_ack: ack,
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
          <PlacePicker id="from" label="From" places={places} value={from} onChange={setFrom} exclude={to?.id} />
          <PlacePicker id="to" label="To" places={places} value={to} onChange={setTo} exclude={from?.id} />

          {from && to && (
            <fieldset>
              <legend className="label">Which way are you driving?</legend>
              {options === null ? (
                <p className="text-sm text-muted">Finding routes</p>
              ) : options.length === 0 ? (
                <p className="rounded-xl bg-warn-wash p-3 text-sm text-warn">
                  No route goes from {from.name} to {to.name} yet. Try the nearest town on a main route, or tell us which road you take.
                </p>
              ) : (
                <div className="grid gap-2">
                  {options.map((o) => (
                    <label key={o.id} className={`block rounded-xl bg-surface p-4 ring-1 ${
                      routeId === o.id ? "ring-2 ring-brand" : "ring-line"} ${o.ready ? "" : "opacity-60"}`}>
                      <span className="flex items-start gap-3">
                        <input type="radio" name="route" className="mt-1 h-5 w-5 accent-brand" disabled={!o.ready}
                          checked={routeId === o.id} onChange={() => { setRouteId(o.id); setDisabled(new Set()); setFareTouched(false); }} />
                        <span className="min-w-0 flex-1">
                          <span className="block font-bold">{distinctLabel(o, options)}</span>
                          {options.length > 1 && <span className="block text-xs text-muted">{o.label}</span>}
                          <span className="block text-sm text-muted tabular-nums">
                            {o.ready ? `${Number(o.distance_km)} km, ${rupees(o.tolls_inr)} tolls${o.minutes ? `, ${hoursLabel(o.minutes)}` : ""}` : "Distances still being checked"}
                          </span>
                        </span>
                      </span>
                    </label>
                  ))}
                </div>
              )}
            </fieldset>
          )}

          <div>
            <label className="label" htmlFor="departure">Leaving at (India time)</label>
            <input id="departure" type="datetime-local" className="field" min={minDeparture()} value={departure}
              onChange={(e) => setDeparture(e.target.value)} required />
            <p className="hint">{departure ? istLabel(departure) : "At least 6 hours from now."}</p>
          </div>
        </div>
      )}

      {step === 1 && from && to && (
        <div className="space-y-5">
          <section className="card">
            <h2 className="mb-1 text-base font-bold">Where will you stop?</h2>
            <p className="mb-3 text-sm text-muted">Untick towns you won&apos;t stop in.</p>
            <RouteDiagram stops={stops} onToggle={(i, on) => {
              const id = stops[i].place_id;
              if (id === undefined) return;
              setDisabled((d) => {
                const next = new Set(d);
                if (on) next.delete(id); else next.add(id);
                return next;
              });
            }} />
          </section>
          <PickupSearch id="pickup" label={`Exact pickup point in ${from.name}`} nearPlaceId={from.id} value={pickup} onChange={setPickup} />
          <div>
            <label className="label" htmlFor="dropoff">Drop-off in {to.name}</label>
            <input id="dropoff" className="field" value={dropoff} onChange={(e) => setDropoff(e.target.value)}
              placeholder="Main bus stand" autoComplete="off" />
          </div>
          <div>
            <label className="label" htmlFor="pd">How to find you</label>
            <textarea id="pd" className="field" rows={2} value={pickupDetails} onChange={(e) => setPickupDetails(e.target.value)}
              placeholder="Gate 2, blue i20. Call when you arrive." />
            <p className="hint">Only confirmed passengers see this and the full pickup address.</p>
          </div>
        </div>
      )}

      {step === 2 && (
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

          {quote ? (
            <div className="rounded-2xl bg-brand-wash p-4">
              <p className="text-sm text-brand">Fair share for each person</p>
              <p className="text-3xl font-extrabold tabular-nums text-brand">{rupees(quote.suggested_fare_inr)}</p>
              <p className="mt-1 text-sm text-muted">
                {Number(quote.distance_km)} km at ₹{quote.fuel_cost_per_km}/km plus {rupees(quote.tolls_inr)} tolls, split {quote.seats_offered + 1} ways including you.
              </p>
            </div>
          ) : (
            <p className="text-sm text-muted">Working out the fair share</p>
          )}

          <div>
            <label className="label" htmlFor="fare">Your fare per seat, {from?.name} to {to?.name}</label>
            <div className="relative">
              <span className="pointer-events-none absolute left-3.5 top-1/2 -translate-y-1/2 text-base font-semibold text-muted">₹</span>
              <input id="fare" type="number" inputMode="numeric" min={0} max={quote?.max_fare_inr} className="field pl-8 text-lg font-bold tabular-nums"
                value={fare} onChange={(e) => { setFareTouched(true); setFare(e.target.value === "" ? "" : Number(e.target.value)); }} />
            </div>
            <p className={`hint ${overCap ? "text-danger" : ""}`}>
              {!quote ? "" : overCap
                ? `Fares stay cost-sharing. The most you can ask is ${rupees(quote.max_fare_inr)}.`
                : `Up to ${rupees(quote.max_fare_inr)}, which is 15% above the fair share.`}
            </p>
          </div>

          <div className="card space-y-3">
            <label className="flex min-h-12 items-start gap-3">
              <input type="checkbox" className="mt-1 h-5 w-5 accent-brand" checked={advanceRequired} disabled={!hasUpi}
                onChange={(e) => setAdvanceRequired(e.target.checked)} />
              <span>
                <span className="block font-semibold">Ask for an advance to lock each seat</span>
                <span className="block text-sm text-muted">
                  {advanceRequired
                    ? `${policy.advance_percent}% of the fare${advance ? `, ${rupees(advance)} a seat,` : ""} paid to you over UPI. Passengers who cancel late lose some or all of it.`
                    : hasUpi
                      ? "No advance. Seats are confirmed when you accept, so late cancellations cost passengers nothing but their record."
                      : "Add your UPI ID in your profile to ask for an advance."}
                </span>
              </span>
            </label>
            <label className="flex min-h-12 items-center gap-3">
              <input type="checkbox" checked={codriverWanted} onChange={(e) => setCodriverWanted(e.target.checked)} className="h-5 w-5 accent-brand" />
              I am looking for a co-driver
            </label>
            {codriverWanted && <p className="rounded-xl bg-paper p-3 text-sm text-muted">Co-drivers book a seat and share driving. The same listed fare and cancellation policy apply. Licence status is self-attested, not verified.</p>}
            {womenOnlyEligible && (
              <label className="flex min-h-12 items-center gap-3">
                <input type="checkbox" checked={womenOnly} onChange={(e) => setWomenOnly(e.target.checked)} className="h-5 w-5 accent-brand" />
                Women only (verified members can request)
              </label>
            )}
          </div>

          <div>
            <label className="label" htmlFor="notes">Anything passengers should know?</label>
            <textarea id="notes" className="field" rows={2} maxLength={500} value={notes} onChange={(e) => setNotes(e.target.value)} placeholder="One tea stop on the way. Please travel light." />
          </div>
        </div>
      )}

      {step === 3 && from && to && route && (
        <div className="space-y-4">
          <section className="card">
            <p className="text-lg font-extrabold">{from.name} to {to.name}</p>
            <p className="text-sm text-muted">{route.label}, {Number(route.distance_km)} km</p>
            <p className="text-sm text-muted">{istLabel(departure)}</p>
            <p className="mb-3 text-sm text-muted">
              {seats} seat{seats > 1 ? "s" : ""} at {typeof fare === "number" ? rupees(fare) : ""}, {advanceRequired ? `${rupees(advance)} advance` : "no advance"}. Pickup at {pickup.name}.
            </p>
            <RouteDiagram stops={stops} />
          </section>
          <div className="card space-y-3 text-sm">
            <p className="text-base font-bold">What you&apos;re agreeing to</p>
            {advanceRequired ? <p>{policy.summary}</p> : (
              <p>This ride has no advance. You confirm passengers when you accept them, and nothing is paid until the trip.</p>
            )}
            <p>If you cancel less than 48 hours before departure, it shows on your public record. Two late cancellations in one festival season pause your posting until the season ends.</p>
          </div>
          <label className="flex min-h-12 items-start gap-3 text-base">
            <input type="checkbox" checked={ack} onChange={(e) => setAck(e.target.checked)} className="mt-1 h-5 w-5 accent-brand" />
            <span>I agree to this for every passenger on this ride.</span>
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
