import Link from "next/link";
import { PageHeader } from "@/components/PageHeader";
import { RideCard } from "@/components/RideCard";
import { api, getMe } from "@/lib/server";
import type { Booking, CityPair, Ride } from "@/lib/types";

type Search = { dir?: string; city?: string; date?: string };

const LIVE = ["requested", "accepted", "advance_claimed", "confirmed"];

/** The next 10 days in IST as YYYY-MM-DD with short labels. */
function dateStrip() {
  const fmt = new Intl.DateTimeFormat("en-CA", { timeZone: "Asia/Kolkata" });
  const label = new Intl.DateTimeFormat("en-IN", { timeZone: "Asia/Kolkata", weekday: "short", day: "numeric" });
  return Array.from({ length: 10 }, (_, i) => {
    const d = new Date(Date.now() + i * 86_400_000);
    return { value: fmt.format(d), label: i === 0 ? "Today" : i === 1 ? "Tomorrow" : label.format(d) };
  });
}

function href(q: Search, patch: Partial<Search>) {
  const next = { ...q, ...patch };
  const p = new URLSearchParams(Object.entries(next).filter(([, v]) => v) as [string, string][]);
  return `/?${p}`;
}

export default async function Home({ searchParams }: { searchParams: Promise<Search> }) {
  const q = await searchParams;
  const dir = q.dir === "pune" ? "pune" : "home";
  const me = await getMe();
  const pairs = await api<CityPair[]>("/city-pairs").catch(() => []);
  const vidarbha = Array.from(new Set(pairs.map((p) => (p.origin === "Pune" ? p.destination : p.origin)))).sort();

  const params = new URLSearchParams();
  if (dir === "home") params.set("origin", "Pune");
  else params.set("destination", "Pune");
  if (q.city) params.set(dir === "home" ? "destination" : "origin", q.city);
  if (q.date) params.set("date", q.date);

  const [rides, bookings] = await Promise.all([
    api<Ride[]>(`/rides?${params}`).catch(() => null),
    me ? api<Booking[]>("/me/bookings").catch(() => []) : Promise.resolve([] as Booking[]),
  ]);
  const next = bookings.find((b) => b.role === "passenger" && LIVE.includes(b.status));

  return (
    <div className="pad-tabbar">
      <PageHeader title="Find a seat" subtitle="Cost-sharing drives between Pune and Vidarbha" />

      {me && !me.profile_complete && (
        <Link href="/me?next=/" className="mb-4 flex items-center justify-between rounded-2xl bg-mile-wash p-4 text-sm">
          <span><b>Finish your profile</b> to book or offer a ride.</span>
          <span className="font-bold text-brand">Finish</span>
        </Link>
      )}

      {next && (
        <Link href={`/bookings/${next.code}`} className="mb-4 block rounded-2xl bg-brand p-4 text-white active:bg-brand-dark">
          <p className="text-sm text-white/80">Your next trip: {next.status_label}</p>
          <p className="mt-0.5 text-lg font-extrabold">{next.ride.origin} to {next.ride.destination}</p>
          <p className="text-sm text-white/85">{next.ride.departure_at.ist}</p>
          {next.actions.some((a) => a === "claim-advance" || a.startsWith("reconfirm") || a === "trip-confirmation") && (
            <p className="mt-2 inline-block rounded-full bg-mile px-3 py-1 text-xs font-bold text-ink">Needs you now</p>
          )}
        </Link>
      )}

      <Link href="/seat-wanted" className="mb-4 flex items-center justify-between gap-3 rounded-2xl bg-mile-wash p-4 active:bg-mile/30">
        <span>
          <span className="block text-sm font-bold">Can&apos;t find a ride?</span>
          <span className="block text-sm text-muted">Post what you need and get an alert when one matches.</span>
        </span>
        <span className="shrink-0 text-sm font-bold text-brand">Set alert</span>
      </Link>

      <section aria-label="Search" className="space-y-3">
        <div className="grid grid-cols-2 gap-1 rounded-2xl bg-line/70 p-1" role="tablist" aria-label="Direction">
          {[
            { key: "home", label: "Pune to home" },
            { key: "pune", label: "Back to Pune" },
          ].map((d) => (
            <Link
              key={d.key}
              role="tab"
              aria-selected={dir === d.key}
              href={href(q, { dir: d.key === "home" ? undefined : "pune" })}
              className={`grid min-h-11 place-items-center rounded-xl text-sm font-bold ${
                dir === d.key ? "bg-surface text-ink shadow-sm" : "text-muted"
              }`}
            >
              {d.label}
            </Link>
          ))}
        </div>

        <div className="scroll-row" aria-label={dir === "home" ? "Going to" : "Leaving from"}>
          <Link href={href(q, { city: undefined })} className="chip" aria-current={!q.city}>All of Vidarbha</Link>
          {vidarbha.map((c) => (
            <Link key={c} href={href(q, { city: c })} className="chip" aria-current={q.city === c}>{c}</Link>
          ))}
        </div>

        <div className="scroll-row" aria-label="Date">
          <Link href={href(q, { date: undefined })} className="chip" aria-current={!q.date}>Any day</Link>
          {dateStrip().map((d) => (
            <Link key={d.value} href={href(q, { date: d.value })} className="chip" aria-current={q.date === d.value}>{d.label}</Link>
          ))}
        </div>
      </section>

      <section className="mt-5 space-y-3" aria-live="polite">
        {rides === null ? (
          <div className="card space-y-3 text-base">
            <p className="text-danger">Rides didn&apos;t load. Check your connection and try again.</p>
            <Link href={href(q, {})} className="btn-secondary">Try again</Link>
          </div>
        ) : rides.length === 0 ? (
          <div className="card space-y-3 text-center">
            <p className="text-base font-semibold">No rides here yet</p>
            <p className="text-sm text-muted">Try another day, or ask in your WhatsApp group and send the driver this app to post the ride.</p>
            <Link href="/rides/new" className="btn-secondary">Driving yourself? Offer seats</Link>
          </div>
        ) : (
          <>
            <p className="text-sm text-muted">{rides.length} ride{rides.length > 1 ? "s" : ""}</p>
            {rides.map((r) => <RideCard key={r.code} ride={r} />)}
          </>
        )}
      </section>
    </div>
  );
}
