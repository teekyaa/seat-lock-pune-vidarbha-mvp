import { notFound } from "next/navigation";
import { Reliability } from "@/components/Reliability";
import { ApiError, api } from "@/lib/server";
import type { PublicUser } from "@/lib/types";

export default async function ProfilePage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  let user: PublicUser;
  try {
    user = await api<PublicUser>(`/users/${encodeURIComponent(id)}`);
  } catch (e) {
    if (e instanceof ApiError && e.status === 404) notFound();
    throw e;
  }
  return (
    <div className="space-y-4">
      <section className="card">
        <h1 className="text-xl font-bold">{user.name || "Member"}</h1>
        <p className="text-sm text-muted">From {user.hometown || "somewhere"} · member since {user.member_since}</p>
        <div className="mt-2 flex gap-2">
          {user.id_verified && <span className="pill bg-brand-wash text-brand">ID checked</span>}
          {user.women_only_verified && <span className="pill bg-pink-50 text-pink-700">Verified for women-only rides</span>}
        </div>
      </section>
      <section className="card space-y-2">
        <h2 className="font-bold">Reliability record</h2>
        <p className="text-xs text-muted">Built from confirmed bookings only. Corrections are added by our team after a review.</p>
        <Reliability record={user.reliability} />
      </section>
    </div>
  );
}
