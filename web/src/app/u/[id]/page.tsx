import { notFound } from "next/navigation";
import { Reliability } from "@/components/Reliability";
import { TopBar } from "@/components/TopBar";
import { ApiError, api } from "@/lib/server";
import type { PublicProfile } from "@/lib/types";
import { VouchPanel } from "./VouchPanel";

export default async function ProfilePage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  let user: PublicProfile;
  try {
    user = await api<PublicProfile>(`/users/${encodeURIComponent(id)}`);
  } catch (e) {
    if (e instanceof ApiError && e.status === 404) notFound();
    throw e;
  }
  return (
    <div className="pad-tabbar">
      <TopBar title="Member" />
      <section className="flex items-center gap-4 pb-5">
        <span className="grid h-16 w-16 place-items-center rounded-full bg-brand-wash text-2xl font-extrabold text-brand">
          {(user.name || "?").slice(0, 1)}
        </span>
        <div>
          <h1 className="text-2xl font-extrabold leading-tight">{user.name || "Member"}</h1>
          <p className="text-base text-muted">From {user.hometown || "somewhere"}, member since {user.member_since.slice(0, 4)}</p>
          <div className="mt-1.5 flex gap-1.5">
            {user.id_verified && <span className="pill bg-brand-wash text-brand">ID checked</span>}
            {user.women_only_verified && <span className="pill bg-pink-50 text-pink-800">Women-only verified</span>}
          </div>
        </div>
      </section>
      <section className="card">
        <h2 className="text-lg font-bold">Reliability record</h2>
        <p className="mb-4 mt-1 text-sm text-muted">Counted from confirmed bookings only. Our team adds corrections after a review.</p>
        <Reliability record={user.reliability} />
      </section>
      <VouchPanel userId={user.id} userName={user.name || "this member"} vouches={user.vouches} />
    </div>
  );
}
