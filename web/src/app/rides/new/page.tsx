import Link from "next/link";
import { redirect } from "next/navigation";
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
  const missing = [
    !me.profile_complete && "finish your profile",
    !me.upi_id && "add your UPI ID",
    vehicles.length === 0 && "add your car",
  ].filter(Boolean);

  return (
    <div className="space-y-4">
      <h1 className="text-2xl font-bold">Offer a ride</h1>
      {missing.length > 0 ? (
        <div className="card space-y-3 text-sm">
          <p>Before you post, please {missing.join(", ")}.</p>
          <Link href="/me?next=/rides/new" className="btn-primary">Go to your profile</Link>
        </div>
      ) : (
        <RideForm pairs={pairs} vehicles={vehicles} policy={policy} womenOnlyEligible={me.women_only_eligible} />
      )}
    </div>
  );
}
