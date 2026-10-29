"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";
import { call } from "@/lib/client";
import type { CityPair, SeatWanted } from "@/lib/types";

export function SeatWantedForm({ pairs, requests, minDate }: {
  pairs: CityPair[];
  requests: SeatWanted[];
  minDate: string;
}) {
  const router = useRouter();
  const [cityPair, setCityPair] = useState(String(pairs[0]?.id ?? ""));
  const [travelDate, setTravelDate] = useState(minDate);
  const [seats, setSeats] = useState("1");
  const [flexDays, setFlexDays] = useState("0");
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");

  async function create(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setBusy(true);
    setMessage("");
    setError("");
    try {
      await call("/seat-wanted", "POST", {
        city_pair: Number(cityPair),
        travel_date: travelDate,
        seats: Number(seats),
        flex_days: Number(flexDays),
      });
      setMessage("Request posted. We’ll alert you when a matching ride appears.");
      router.refresh();
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setBusy(false);
    }
  }

  async function close(id: number) {
    setBusy(true);
    setError("");
    setMessage("");
    try {
      await call(`/seat-wanted/${id}`, "DELETE");
      setMessage("Request closed. New ride alerts for it have stopped.");
      router.refresh();
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="space-y-4">
      <form onSubmit={create} className="card space-y-4">
        <div>
          <label className="label" htmlFor="wanted-route">Route</label>
          <select id="wanted-route" className="field" value={cityPair} onChange={(event) => setCityPair(event.target.value)} required>
            {pairs.map((pair) => <option key={pair.id} value={pair.id}>{pair.origin} to {pair.destination}</option>)}
          </select>
        </div>
        <div>
          <label className="label" htmlFor="wanted-date">Travel date</label>
          <input id="wanted-date" className="field" type="date" min={minDate} value={travelDate}
            onChange={(event) => setTravelDate(event.target.value)} required />
        </div>
        <div className="grid grid-cols-2 gap-3">
          <div>
            <label className="label" htmlFor="wanted-seats">Seats needed</label>
            <select id="wanted-seats" className="field" value={seats} onChange={(event) => setSeats(event.target.value)}>
              {[1, 2, 3, 4, 5, 6, 7].map((n) => <option key={n} value={n}>{n}</option>)}
            </select>
          </div>
          <div>
            <label className="label" htmlFor="wanted-flex">Date flexibility</label>
            <select id="wanted-flex" className="field" value={flexDays} onChange={(event) => setFlexDays(event.target.value)}>
              <option value="0">Exact date</option>
              <option value="1">±1 day</option>
              <option value="2">±2 days</option>
              <option value="3">±3 days</option>
            </select>
          </div>
        </div>
        <p className="text-xs text-muted">Alerts appear in your inbox. Email or web push is also sent where configured.</p>
        {error && <p role="alert" className="rounded-xl bg-danger-wash p-3 text-sm text-danger">{error}</p>}
        {message && <p role="status" className="rounded-xl bg-brand-wash p-3 text-sm text-brand">{message}</p>}
        <button className="btn-primary w-full" disabled={busy || pairs.length === 0 || !cityPair}>
          {busy ? "Saving…" : "Create ride alert"}
        </button>
      </form>

      <section className="card space-y-3">
        <div>
          <h2 className="text-lg font-bold">Your active requests</h2>
          <p className="text-sm text-muted">Close a request when you no longer need a ride.</p>
        </div>
        {requests.length === 0 ? <p className="text-sm text-muted">No active requests yet.</p> : (
          <ul className="divide-y divide-line">
            {requests.map((request) => (
              <li key={request.id} className="flex items-center justify-between gap-3 py-3">
                <div className="min-w-0">
                  <p className="font-semibold">{request.origin} to {request.destination}</p>
                  <p className="text-sm text-muted">
                    {request.travel_date} · {request.seats} seat{request.seats === 1 ? "" : "s"} · {request.flex_days ? `±${request.flex_days} days` : "exact date"}
                  </p>
                </div>
                <button type="button" className="btn-ghost min-h-10 px-2 text-sm" disabled={busy} onClick={() => close(request.id)}>
                  Close
                </button>
              </li>
            ))}
          </ul>
        )}
      </section>
    </div>
  );
}
