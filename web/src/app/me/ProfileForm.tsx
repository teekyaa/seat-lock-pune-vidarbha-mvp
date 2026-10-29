"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { ChevronIcon } from "@/components/icons";
import { PageHeader } from "@/components/PageHeader";
import { PushToggle } from "@/components/PushToggle";
import { ConfirmSheet, Sheet } from "@/components/Sheet";
import { call } from "@/lib/client";
import type { Me, Vehicle } from "@/lib/types";

const TOWNS = ["Nagpur", "Wardha", "Chandrapur", "Amravati", "Yavatmal", "Akola", "Pune", "Other"];

type Form = Pick<Me, "name" | "hometown" | "gender" | "college_or_workplace" | "email" | "upi_id">;

export function ProfileForm({ me, vehicles, next }: { me: Me; vehicles: Vehicle[]; next?: string }) {
  const router = useRouter();
  const [form, setForm] = useState<Form>({
    name: me.name, hometown: me.hometown, gender: me.gender, college_or_workplace: me.college_or_workplace,
    email: me.email, upi_id: me.upi_id,
  });
  const [accept, setAccept] = useState(Boolean(me.terms_accepted_at));
  const [car, setCar] = useState({ make_model: "", colour: "", registration: "", passenger_seats: 4 });
  const [carOpen, setCarOpen] = useState(false);
  const [removeCar, setRemoveCar] = useState<Vehicle | null>(null);
  const [saved, setSaved] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const onboarding = !me.profile_complete;

  const set = (k: keyof Form) => (e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement>) => {
    setForm({ ...form, [k]: e.target.value });
    setSaved("");
  };

  async function run(fn: () => Promise<unknown>, done?: string) {
    setBusy(true);
    setError("");
    try {
      await fn();
      if (done) setSaved(done);
      router.refresh();
      return true;
    } catch (err) {
      setError((err as Error).message);
      return false;
    } finally {
      setBusy(false);
    }
  }

  async function save(e: React.FormEvent) {
    e.preventDefault();
    await run(async () => {
      const updated = await call<Me>("/me", "PATCH", { ...form, accept_terms: accept });
      if (updated.profile_complete && next) router.push(next);
    }, "Saved");
  }

  const field = (k: keyof Form, label: string, props: React.InputHTMLAttributes<HTMLInputElement> = {}, hint?: string) => (
    <div>
      <label className="label" htmlFor={k}>{label}</label>
      <input id={k} className="field" value={form[k]} onChange={set(k)} {...props} />
      {hint && <p className="hint">{hint}</p>}
    </div>
  );

  const profileFields = (
    <>
      {field("name", "Full name", { required: true, maxLength: 80, autoComplete: "name" })}
      <div>
        <span className="label">Hometown</span>
        <div className="flex flex-wrap gap-2">
          {TOWNS.map((t) => (
            <button type="button" key={t} className="chip" aria-current={form.hometown === t}
              onClick={() => { setForm({ ...form, hometown: t }); setSaved(""); }}>{t}</button>
          ))}
        </div>
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
      {field("college_or_workplace", "College or workplace (optional)", { maxLength: 120 }, "Helps people from the same place find each other.")}
    </>
  );

  if (onboarding) {
    return (
      <form onSubmit={save} className="pad-tabbar">
        <PageHeader title="Welcome" subtitle="A few details so drivers and passengers know who they're travelling with." />
        <div className="space-y-5">
          {profileFields}
          <label className="flex min-h-12 items-start gap-3 rounded-xl bg-surface p-4 text-base ring-1 ring-line">
            <input type="checkbox" checked={accept} onChange={(e) => setAccept(e.target.checked)} className="mt-1 h-5 w-5 accent-brand" />
            <span>I&apos;ll share travel costs only, never charge for profit, and follow the community rules.</span>
          </label>
          {error && <p className="rounded-xl bg-danger-wash p-3 text-sm text-danger" role="alert">{error}</p>}
          <button className="btn-primary w-full" disabled={busy || !form.name || !form.hometown || !accept}>
            {busy ? "Saving" : "Continue"}
          </button>
          <p className="text-center text-sm text-muted">Signed in as {me.phone}</p>
        </div>
      </form>
    );
  }

  return (
    <div className="pad-tabbar space-y-5">
      <PageHeader title="Me" />
      <Link href={`/u/${me.id}`} className="card flex items-center gap-3 active:bg-paper">
        <span className="grid h-14 w-14 place-items-center rounded-full bg-brand-wash text-xl font-extrabold text-brand">{me.name.slice(0, 1)}</span>
        <span className="flex-1">
          <span className="block text-lg font-bold">{me.name}</span>
          <span className="block text-sm text-muted">{me.phone}. See your public record</span>
        </span>
        <ChevronIcon className="h-5 w-5 text-muted" />
      </Link>

      <form onSubmit={save} className="space-y-5">
        <section className="card space-y-5">
          <h2 className="text-lg font-bold">About you</h2>
          {profileFields}
          {me.women_only_eligible && <p className="pill bg-pink-50 text-pink-800">Verified for women-only rides</p>}
        </section>

        <section className="card space-y-5">
          <h2 className="text-lg font-bold">Payments and reminders</h2>
          {field("upi_id", "UPI ID", { placeholder: "name@okaxis", autoCapitalize: "none", autoCorrect: "off", spellCheck: false },
            "Passengers pay your advance here. As a passenger, refunds come here.")}
          {field("email", "Email for reminders", { type: "email", autoComplete: "email", inputMode: "email" })}
        </section>

        {error && <p className="rounded-xl bg-danger-wash p-3 text-sm text-danger" role="alert">{error}</p>}
        <button className="btn-primary w-full" disabled={busy}>{busy ? "Saving" : saved || "Save changes"}</button>
      </form>

      <section className="card space-y-3">
        <div className="flex items-center justify-between">
          <h2 className="text-lg font-bold">Your cars</h2>
          <button className="btn-ghost min-h-10 px-3" onClick={() => setCarOpen(true)}>Add car</button>
        </div>
        {vehicles.length === 0 && <p className="text-sm text-muted">Add a car to offer seats.</p>}
        <ul className="divide-y divide-line">
          {vehicles.map((v) => (
            <li key={v.id} className="flex min-h-14 items-center justify-between gap-3">
              <span>
                <span className="block font-semibold">{v.colour} {v.make_model}</span>
                <span className="block text-sm text-muted">{v.registration}, {v.passenger_seats} passenger seats</span>
              </span>
              <button className="min-h-11 px-2 text-sm font-semibold text-danger" onClick={() => setRemoveCar(v)}>Remove</button>
            </li>
          ))}
        </ul>
        <p className="hint">Only confirmed passengers see your registration number.</p>
      </section>

      <section className="card space-y-3">
        <h2 className="text-lg font-bold">Reminders on this phone</h2>
        <PushToggle />
      </section>

      <button className="btn-secondary w-full" onClick={async () => {
        await fetch("/session", { method: "DELETE" });
        router.replace("/");
        router.refresh();
      }}>Sign out</button>

      <Sheet open={carOpen} onClose={() => setCarOpen(false)} title="Add a car">
        <form className="space-y-4" onSubmit={async (e) => {
          e.preventDefault();
          if (await run(() => call("/me/vehicles", "POST", car))) {
            setCar({ make_model: "", colour: "", registration: "", passenger_seats: 4 });
            setCarOpen(false);
          }
        }}>
          <div>
            <label className="label" htmlFor="mm">Make and model</label>
            <input id="mm" className="field" placeholder="Maruti Ertiga" value={car.make_model} onChange={(e) => setCar({ ...car, make_model: e.target.value })} required />
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="label" htmlFor="col">Colour</label>
              <input id="col" className="field" placeholder="White" value={car.colour} onChange={(e) => setCar({ ...car, colour: e.target.value })} />
            </div>
            <div>
              <label className="label" htmlFor="reg">Registration</label>
              <input id="reg" className="field uppercase" placeholder="MH12AB1234" autoCapitalize="characters" value={car.registration}
                onChange={(e) => setCar({ ...car, registration: e.target.value })} required />
            </div>
          </div>
          <div>
            <span className="label">Seats for passengers</span>
            <div className="flex flex-wrap gap-2">
              {[1, 2, 3, 4, 5, 6, 7].map((n) => (
                <button type="button" key={n} className="chip w-12" aria-current={car.passenger_seats === n}
                  onClick={() => setCar({ ...car, passenger_seats: n })}>{n}</button>
              ))}
            </div>
          </div>
          {error && <p className="text-sm text-danger" role="alert">{error}</p>}
          <button className="btn-primary w-full" disabled={busy}>Save car</button>
        </form>
      </Sheet>

      <ConfirmSheet open={Boolean(removeCar)} onClose={() => setRemoveCar(null)} title="Remove this car?" danger busy={busy}
        confirmLabel="Remove" onConfirm={async () => { if (removeCar && (await run(() => call(`/me/vehicles/${removeCar.id}`, "DELETE")))) setRemoveCar(null); }}
        body={<><p>{removeCar?.colour} {removeCar?.make_model}, {removeCar?.registration}</p>{error && <p className="text-sm text-danger">{error}</p>}</>} />
    </div>
  );
}
