import { ImageResponse } from "next/og";

/** The app icon: a milestone in sign green. `pad` leaves room for Android's maskable crop. */
export function appIcon(size: number, pad = 0.18) {
  const inner = Math.round(size * (1 - pad * 2));
  return new ImageResponse(
    (
      <div style={{ width: "100%", height: "100%", display: "flex", alignItems: "center", justifyContent: "center", background: "#0d6a4e" }}>
        <div style={{ width: inner * 0.62, height: inner * 0.8, display: "flex", flexDirection: "column", background: "#ffffff",
          borderTopLeftRadius: inner * 0.31, borderTopRightRadius: inner * 0.31, overflow: "hidden" }}>
          <div style={{ height: "42%", background: "#f4b400", display: "flex" }} />
          <div style={{ flex: 1, display: "flex", alignItems: "center", justifyContent: "center" }}>
            <div style={{ width: inner * 0.2, height: inner * 0.2, borderRadius: inner * 0.04, background: "#13201a", display: "flex" }} />
          </div>
        </div>
      </div>
    ),
    { width: size, height: size },
  );
}
