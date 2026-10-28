import { ImageResponse } from "next/og";
import { API_URL } from "@/lib/server";
import type { Ride } from "@/lib/types";

export const alt = "Seat Lock ride";
export const size = { width: 1200, height: 630 };
export const contentType = "image/png";

// Per-ride preview card so WhatsApp shows the route, time, fare and seats.
// Satori needs one text node per element, and its default font has no rupee glyph, so "Rs" is used.
export default async function Image({ params }: { params: Promise<{ code: string }> }) {
  const { code } = await params;
  const res = await fetch(`${API_URL}/api/v1/rides/${encodeURIComponent(code)}`, { next: { revalidate: 300 } });
  const ride: Ride | null = res.ok ? await res.json() : null;

  return new ImageResponse(
    (
      <div style={{ width: "100%", height: "100%", display: "flex", flexDirection: "column", justifyContent: "space-between",
        padding: 64, background: "#0d6a4e", color: "white", fontFamily: "sans-serif" }}>
        <div style={{ fontSize: 34, fontWeight: 700, opacity: 0.85 }}>Seat Lock · cost-sharing carpool</div>
        {ride ? (
          <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
            <div style={{ fontSize: 84, fontWeight: 800 }}>{`${ride.origin} to ${ride.destination}`}</div>
            <div style={{ fontSize: 44 }}>{ride.departure_at.ist}</div>
          </div>
        ) : (
          <div style={{ fontSize: 72, fontWeight: 800 }}>Pune to Vidarbha carpools</div>
        )}
        {ride && (
          <div style={{ display: "flex", gap: 24, fontSize: 40 }}>
            <div style={{ background: "white", color: "#0d6a4e", borderRadius: 24, padding: "12px 28px", fontWeight: 800 }}>
              {`Rs ${ride.fare_inr} a seat`}
            </div>
            <div style={{ background: "rgba(255,255,255,0.15)", borderRadius: 24, padding: "12px 28px" }}>
              {ride.status === "cancelled" ? "Cancelled" : ride.seats_left > 0 ? `${ride.seats_left} seats left` : "Full, waitlist open"}
            </div>
            <div style={{ background: "rgba(255,255,255,0.15)", borderRadius: 24, padding: "12px 28px" }}>{ride.driver.name}</div>
          </div>
        )}
      </div>
    ),
    size,
  );
}
