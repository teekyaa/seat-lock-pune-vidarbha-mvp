"use client";

import { useEffect, useState } from "react";
import { call } from "@/lib/client";
import type { When } from "@/lib/types";

type IssuedLink = { token: string; expires_at: When };

export function TripShareCard({ bookingCode }: { bookingCode: string }) {
  const [link, setLink] = useState("");
  const [expiresAt, setExpiresAt] = useState("");
  const [busy, setBusy] = useState(false);
  const [notice, setNotice] = useState("");
  const [error, setError] = useState("");
  const [localOnly, setLocalOnly] = useState(false);

  useEffect(() => {
    setLocalOnly(["localhost", "127.0.0.1"].includes(window.location.hostname));
  }, []);

  async function createLink() {
    setBusy(true);
    setError("");
    setNotice("");
    try {
      const issued = await call<IssuedLink>(`/bookings/${encodeURIComponent(bookingCode)}/trip-share`, "POST");
      setLink(new URL(`/trip/${encodeURIComponent(issued.token)}`, window.location.origin).toString());
      setExpiresAt(issued.expires_at.ist);
      setNotice("A new private trip link is ready. Any earlier link for this booking has stopped working.");
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setBusy(false);
    }
  }

  async function shareLink() {
    if (!link) return;
    setError("");
    try {
      if (navigator.share) {
        await navigator.share({ title: "My Seat Lock trip", text: "Here are my trip details.", url: link });
      } else {
        await navigator.clipboard.writeText(link);
        setNotice("Link copied. Send it privately to your emergency contact.");
      }
    } catch (err) {
      if (err instanceof Error && err.name === "AbortError") return;
      setError("Sharing did not open. Copy the link below and send it privately.");
    }
  }

  async function copyLink() {
    try {
      await navigator.clipboard.writeText(link);
      setNotice("Link copied. Send it privately to your emergency contact.");
      setError("");
    } catch {
      setNotice("Select and copy the link, then send it privately to your emergency contact.");
    }
  }

  async function revokeLink() {
    setBusy(true);
    setError("");
    setNotice("");
    try {
      await call(`/bookings/${encodeURIComponent(bookingCode)}/trip-share`, "DELETE");
      setLink("");
      setExpiresAt("");
      setNotice("Trip link turned off.");
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <section className="card mt-3 space-y-3 border-brand/30">
      <div>
        <p className="text-base font-bold">Share your trip safely</p>
        <p className="mt-1 text-sm text-muted">
          Make a private link for someone you trust. It shows the driver, car, route and departure time, and expires 24 hours after expected arrival.
        </p>
      </div>

      {link ? (
        <>
          <label className="label" htmlFor={`trip-share-${bookingCode}`}>Private trip link</label>
          <input id={`trip-share-${bookingCode}`} className="field text-sm" value={link} readOnly onFocus={(event) => event.currentTarget.select()} />
          <p className="text-xs text-muted">Available until {expiresAt}. Anyone with the link can see these trip details. Don&apos;t post it publicly.</p>
          {localOnly && <p className="rounded-xl bg-warn-wash p-3 text-sm text-warn">This local demo link only opens on this device. Deploy the app before sharing with someone on another device.</p>}
          <div className="grid grid-cols-2 gap-2">
            <button type="button" className="btn-primary" onClick={shareLink}>Share link</button>
            <button type="button" className="btn-secondary" onClick={copyLink}>Copy link</button>
          </div>
          <button type="button" className="btn-ghost w-full" disabled={busy} onClick={revokeLink}>Turn off this link</button>
        </>
      ) : (
        <button type="button" className="btn-primary w-full" disabled={busy} onClick={createLink}>
          {busy ? "Creating link…" : "Create trip link"}
        </button>
      )}

      {notice && <p role="status" className="text-sm text-brand">{notice}</p>}
      {error && <p role="alert" className="text-sm text-danger">{error}</p>}
      <p className="text-xs text-muted">Only your confirmed booking can create or turn off the link. Seat Lock does not contact anyone for you.</p>
    </section>
  );
}
