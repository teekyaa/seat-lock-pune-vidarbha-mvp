import { redirect } from "next/navigation";
import { api, getMe } from "@/lib/server";
import type { Vehicle } from "@/lib/types";
import { ProfileForm } from "./ProfileForm";

export const metadata = { title: "Your profile" };

export default async function MePage({ searchParams }: { searchParams: Promise<{ next?: string }> }) {
  const me = await getMe();
  if (!me) redirect("/login?next=/me");
  const [vehicles, { next }] = await Promise.all([api<Vehicle[]>("/me/vehicles"), searchParams]);
  return <ProfileForm me={me} vehicles={vehicles} next={next} />;
}
