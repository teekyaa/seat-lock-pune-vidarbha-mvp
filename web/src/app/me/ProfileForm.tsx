"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { PushToggle } from "@/components/PushToggle";
import { call } from "@/lib/client";
import type { Me, Vehicle } from "@/lib/types";

const TOWNS = ["Pune", "Nagpur", "Wardha", "Chandrapur", "Amravati", "Yavatmal", "Other"];

export function ProfileForm({ me, vehicles, next }: { me: Me; vehicles: Vehicle[]; next?: string }) {
  const router = useRouter();
  const [form, setForm] = useState({
    name: me.name, hometown: me.hometown, gender: me.gender, college_or_workplace: me.college_or_workplace,
    email: me.email, upi_id: me.upi_id,
  });
  const [accept, setAccept] = useState(Boolean(me.terms_accepted_at));
  const [car, setCar] = useState({ make_model: "", colour: "", registration: "", passenger_seats: 3 });
  const [msg, setMsg] = useState("");
  const [error, setError] = useState("");

  const set = (k: keyof typeof form) => (e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement>) =>
    setForm({ ...form, [k]: e.target.value });

  async function save(e: React.FormEvent) {
    e.preventDefault();
    setError("");
    try {
      const updated = await call<Me>("/me", "PATCH", { ...form, accept_terms: accept });
      setMsg("Saved.");
      router.refresh();
      if (updated.profile_complete && next) router.push(next);
    } catch (err) {
      setError((err as Error).message);
    }
  }

  async function addCar(e: React.FormEvent) {
    e.preventDefault();
    setError("");
    try {
      await call("/me/vehicles", "POST", car);
      setCar({ make_model: "", colour: "", registration: "", passenger_seats: 3 });
      router.refresh();
    } catch (err) {
      setError((err as Error).message);
    }
  }

  async function removeCar(id: number) {
    try {
      await call(`/me/vehicles/${id}`, "DELETE");
      router.refresh();
    } catch (err) {
      setError((err as Error).message);
    }
  }

  async function signOut() {
    await fetch("/session", { method: "DELETE" });
    router.push("/");
    router.refresh();
  }

  return (
    <div className="space-y-5">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold">Your profile</h1>
        <Link href={`/u/${me.id}`} className="text-sm font-semibold text-brand">See your public record</Link>
      </div>

      <form onSubmit={save} className="card space-y-3">
        <p className="text-sm text-muted">Signed in as {me.phone}. Your number is only shown to people on a confirmed booking with you.</p>
        <div>
          <label className="label" htmlFor="name">Full name</label>
          <input id="name" className="field" value={form.name} onChange={set("name")} required maxLength={80} />
        </div>
        <div className="grid grid-cols-2 gap-3">
          <div>
            <label className="label" htmlFor="hometown">Hometown</label>
            <select id="hometown" className="field" value={form.hometown} onChange={set("hometown")} required>
              <option value="">Choose</option>
              {TOWNS.map((t) => <option key={t}>{t}</option>)}
            </select>
          </div>
          <div>
            <label className="label" htmlFor="gender">Gender</label>
            <select id="gender" className="field" value={form.gender} onChange={set("gender")}>
              <option value="female">Female</option>
              <option value="male">Male</option>
              <option value="other">Other</option>
              <option value="undisclosed">Prefer not to say</option>
            </select>
          </div>
        </div>
        <div>
          <label className="label" htmlFor="work">College or workplace</label>
          <input id="work" className="field" value={form.college_or_workplace} onChange={set("college_or_workplace")} maxLength={120} />
        </div>
        <div>
          <label className="label" htmlFor="upi">UPI ID</label>
          <input id="upi" className="field" value={form.upi_id} onChange={set("upi_id")} placeholder="name@okaxis" />
          <p className="hint">Drivers need this so passengers can pay the advance. Passengers need it for refunds.</p>
        </div>
        <div>
          <label className="label" htmlFor="email">Email for trip reminders</label>
          <input id="email" type="email" className="field" value={form.email} onChange={set("email")} />
        </div>
        {me.women_only_eligible && <p className="pill bg-pink-50 text-pink-700">Verified for women-only rides</p>}
        <label className="flex items-start gap-2 text-sm">
          <input type="checkbox" checked={accept} onChange={(e) => setAccept(e.target.checked)} disabled={Boolean(me.terms_accepted_at)} className="mt-1" />
          <span>I agree to share costs only, never to make a profit, and to the Seat Lock community rules.</span>
        </label>
        <button className="btn-primary w-full">Save profile</button>
        {msg && <p className="text-sm text-brand">{msg}</p>}
      </form>

      <section className="card space-y-3">
        <h2 className="font-bold">Your cars</h2>
        {vehicles.length === 0 && <p className="text-sm text-muted">Add a car to offer rides.</p>}
        {vehicles.map((v) => (
          <div key={v.id} className="flex items-center justify-between rounded-xl bg-paper p-3 text-sm">
            <span>{v.colour} {v.make_model} · {v.registration} · {v.passenger_seats} seats</span>
            <button className="text-danger" onClick={() => removeCar(v.id)}>Remove</button>
          </div>
        ))}
        <form onSubmit={addCar} className="grid grid-cols-2 gap-2">
          <input className="field col-span-2" placeholder="Make and model, e.g. Maruti Ertiga" value={car.make_model}
            onChange={(e) => setCar({ ...car, make_model: e.target.value })} required />
          <input className="field" placeholder="Colour" value={car.colour} onChange={(e) => setCar({ ...car, colour: e.target.value })} />
          <input className="field" placeholder="MH12AB1234" value={car.registration}
            onChange={(e) => setCar({ ...car, registration: e.target.value })} required />
          <label className="col-span-2 text-sm">
            Passenger seats
            <input type="number" min={1} max={7} className="field mt-1" value={car.passenger_seats}
              onChange={(e) => setCar({ ...car, passenger_seats: Number(e.target.value) })} />
          </label>
          <button className="btn-secondary col-span-2">Add car</button>
        </form>
        <p className="hint">Your registration number is only shown to confirmed passengers.</p>
      </section>

      <section className="card space-y-3">
        <h2 className="font-bold">Reminders on this phone</h2>
        <PushToggle />
      </section>

      {error && <p className="text-sm text-danger" role="alert">{error}</p>}
      <button className="btn-secondary w-full" onClick={signOut}>Sign out</button>
    </div>
  );
}
