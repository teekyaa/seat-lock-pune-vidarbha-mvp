import Link from "next/link";
import { redirect } from "next/navigation";
import { TopBar } from "@/components/TopBar";
import { api, getMe } from "@/lib/server";
import type { CityPair, Policy, Vehicle } from "@/lib/types";
import { RideForm } from "./RideForm";

export const metadata = { title: "Offer a ride" };

export default async function NewRidePage() {
  const me = await getMe();
  if (!me) redirect("/login?next=/rides/new");
  const [pairs, vehicles, policy] = await Promise.all([
    api<CityPair[]>("/city-pairs"),
    api<Vehicle[]>("/me/vehicles"),
    api<Policy>("/policy"),
  ]);
  const todo = [
    { done: me.profile_complete, label: "Finish your profile" },
    { done: Boolean(me.upi_id), label: "Add your UPI ID, so passengers can pay the advance" },
    { done: vehicles.length > 0, label: "Add the car you'll drive" },
  ];

  return (
    <div>
      <TopBar title="Offer a ride" />
      {todo.some((t) => !t.done) ? (
        <div className="space-y-4">
          <p className="text-xl font-extrabold">Before you post</p>
          <ul className="card divide-y divide-line p-0">
            {todo.map((t) => (
              <li key={t.label} className="flex min-h-14 items-center gap-3 px-4">
                <span className={`grid h-6 w-6 place-items-center rounded-full text-xs font-bold ${t.done ? "bg-brand text-white" : "bg-line text-muted"}`}>
                  {t.done ? "✓" : ""}
                </span>
                <span className={t.done ? "text-muted line-through" : "font-semibold"}>{t.label}</span>
              </li>
            ))}
          </ul>
          <Link href="/me?next=/rides/new" className="btn-primary w-full">Go to your profile</Link>
        </div>
      ) : (
        <RideForm pairs={pairs} vehicles={vehicles} policy={policy} womenOnlyEligible={me.women_only_eligible} />
      )}
    </div>
  );
}
