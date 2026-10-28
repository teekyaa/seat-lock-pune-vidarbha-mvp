import { RideCard } from "@/components/RideCard";
import { api } from "@/lib/server";
import type { CityPair, Ride } from "@/lib/types";

type Search = { origin?: string; destination?: string; date?: string };

export default async function Home({ searchParams }: { searchParams: Promise<Search> }) {
  const q = await searchParams;
  const params = new URLSearchParams(Object.entries(q).filter(([, v]) => v) as [string, string][]);
  const [pairs, rides] = await Promise.all([
    api<CityPair[]>("/city-pairs").catch(() => []),
    api<Ride[]>(`/rides?${params}`).catch(() => null),
  ]);
  const cities = Array.from(new Set(pairs.flatMap((p) => [p.origin, p.destination]))).sort();

  return (
    <div className="space-y-5">
      <section className="rounded-3xl bg-brand px-5 py-6 text-white">
        <h1 className="text-2xl font-bold leading-tight">Going home to Vidarbha? Share the drive.</h1>
        <p className="mt-2 text-sm text-white/80">
          Cost-sharing carpools between Pune and Nagpur, Wardha or Chandrapur. A small UPI advance locks your seat, so
          plans don&apos;t fall apart at the last minute.
        </p>
        <form className="mt-4 grid grid-cols-2 gap-2 sm:grid-cols-4" action="/">
          <select name="origin" defaultValue={q.origin ?? ""} className="field text-ink" aria-label="From">
            <option value="">From anywhere</option>
            {cities.map((c) => <option key={c}>{c}</option>)}
          </select>
          <select name="destination" defaultValue={q.destination ?? ""} className="field text-ink" aria-label="To">
            <option value="">To anywhere</option>
            {cities.map((c) => <option key={c}>{c}</option>)}
          </select>
          <input type="date" name="date" defaultValue={q.date ?? ""} className="field text-ink" aria-label="Date" />
          <button className="btn bg-white text-brand hover:bg-brand-wash">Search</button>
        </form>
      </section>

      {rides === null ? (
        <p className="card text-sm text-danger">We couldn&apos;t load rides right now. Please try again in a minute.</p>
      ) : rides.length === 0 ? (
        <div className="card text-sm text-muted">
          No rides match yet. Try another date, or check the WhatsApp group and ask the driver to post here.
        </div>
      ) : (
        <div className="space-y-3">
          {rides.map((r) => <RideCard key={r.code} ride={r} />)}
        </div>
      )}
    </div>
  );
}
