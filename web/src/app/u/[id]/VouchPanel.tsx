"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { call } from "@/lib/client";
import type { VouchProfile } from "@/lib/types";

export function VouchPanel({ userId, userName, vouches }: {
  userId: string;
  userName: string;
  vouches: VouchProfile;
}) {
  const router = useRouter();
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const viewer = vouches.viewer;

  async function updateVouch(method: "POST" | "DELETE", targetId = userId) {
    setBusy(true);
    setError("");
    try {
      await call(`/users/${encodeURIComponent(targetId)}/vouch`, method);
      router.refresh();
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="mt-3 space-y-3">
      <section className="card space-y-3">
        <div>
          <h2 className="text-lg font-bold">Vouches</h2>
          <p className="mt-1 text-sm text-muted">A personal vouch means someone knows this member. It is not identity verification or a safety guarantee.</p>
        </div>
        {vouches.received.length ? (
          <ul className="divide-y divide-line">
            {vouches.received.map((person) => (
              <li key={person.id} className="py-2 text-sm">
                <Link className="font-semibold text-brand underline decoration-line underline-offset-4" href={`/u/${person.id}`}>
                  {person.name || "Member"}
                </Link>
                {person.hometown && <span className="text-muted"> · {person.hometown}</span>}
              </li>
            ))}
          </ul>
        ) : <p className="text-sm text-muted">No active vouches yet.</p>}

        {viewer.is_authenticated && !viewer.is_self && viewer.can_vouch && (
          viewer.has_vouched ? (
            <button type="button" className="btn-secondary w-full" disabled={busy} onClick={() => updateVouch("DELETE")}>
              {busy ? "Saving…" : "Withdraw your vouch"}
            </button>
          ) : viewer.active_given_count >= 5 ? (
            <p className="rounded-xl bg-warn-wash p-3 text-sm text-warn">You have five active vouches. Withdraw one before vouching for someone else.</p>
          ) : (
            <button type="button" className="btn-primary w-full" disabled={busy} onClick={() => updateVouch("POST")}>
              {busy ? "Saving…" : `Vouch for ${userName}`}
            </button>
          )
        )}
        {!viewer.is_authenticated && (
          <Link className="btn-secondary w-full" href={`/login?next=${encodeURIComponent(`/u/${userId}`)}`}>Sign in to vouch</Link>
        )}
      </section>

      {vouches.given.length > 0 && (
        <section className="card space-y-3">
          <div>
            <h2 className="text-lg font-bold">People {viewer.is_self ? "you" : userName} vouch for</h2>
            <p className="mt-1 text-sm text-muted">Late cancellations by vouched members after the vouch are listed here.</p>
          </div>
          <ul className="divide-y divide-line">
            {vouches.given.map((person) => (
              <li key={person.id} className="flex items-center justify-between gap-3 py-3">
                <div className="min-w-0 text-sm">
                  <Link className="font-semibold text-brand underline decoration-line underline-offset-4" href={`/u/${person.id}`}>
                    {person.name || "Member"}
                  </Link>
                  {person.hometown && <span className="text-muted"> · {person.hometown}</span>}
                  <p className={person.late_cancellations_since_vouch ? "mt-1 font-semibold text-warn" : "mt-1 text-muted"}>
                    {person.late_cancellations_since_vouch} late cancellations since vouched
                  </p>
                </div>
                {viewer.is_self && (
                  <button type="button" className="btn-ghost min-h-10 px-2 text-sm" disabled={busy}
                    onClick={() => updateVouch("DELETE", person.id)}>
                    Withdraw
                  </button>
                )}
              </li>
            ))}
          </ul>
        </section>
      )}
      {error && <p role="alert" className="rounded-xl bg-danger-wash p-3 text-sm text-danger">{error}</p>}
      {viewer.is_self && <p className="px-1 text-xs text-muted">You can keep up to five active vouches for people you know.</p>}
    </div>
  );
}
