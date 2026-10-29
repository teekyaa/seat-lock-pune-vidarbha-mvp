import { redirect } from "next/navigation";
import { TopBar } from "@/components/TopBar";
import { api, getMe } from "@/lib/server";
import type { CityPair, SeatWanted } from "@/lib/types";
import { SeatWantedForm } from "./SeatWantedForm";

export const metadata = { title: "Find a ride alert" };

function todayInIst() {
  return new Intl.DateTimeFormat("en-CA", { timeZone: "Asia/Kolkata" }).format(new Date());
}

export default async function SeatWantedPage() {
  const me = await getMe();
  if (!me) redirect("/login?next=%2Fseat-wanted");
  const [pairs, requests] = await Promise.all([
    api<CityPair[]>("/city-pairs"),
    api<SeatWanted[]>("/me/seat-wanted"),
  ]);
  return (
    <main className="pad-tabbar space-y-4">
      <TopBar title="Find a ride alert" />
      <div>
        <h1 className="text-2xl font-extrabold">Tell us what you need</h1>
        <p className="mt-1 text-sm text-muted">We&apos;ll alert you when a ride matches your route, seat count and date window.</p>
      </div>
      <SeatWantedForm pairs={pairs} requests={requests} minDate={todayInIst()} />
    </main>
  );
}
