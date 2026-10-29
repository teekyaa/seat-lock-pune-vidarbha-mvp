import type { Metadata, Viewport } from "next";
import { Overpass } from "next/font/google";
import { RegisterServiceWorker } from "@/components/RegisterServiceWorker";
import { TabBar } from "@/components/TabBar";
import { api, getMe } from "@/lib/server";
import "./globals.css";

// Overpass descends from Highway Gothic, the lettering of road signs.
const overpass = Overpass({ variable: "--font-overpass", subsets: ["latin"], weight: ["400", "600", "700", "800"] });

export const metadata: Metadata = {
  metadataBase: new URL(process.env.NEXT_PUBLIC_SITE_URL ?? "http://localhost:3000"),
  title: { default: "Seat Lock: Pune to Vidarbha carpools", template: "%s · Seat Lock" },
  description: "Share the cost of the drive between Pune and Nagpur, Wardha or Chandrapur. Every seat is locked with a small UPI advance.",
  applicationName: "Seat Lock",
  appleWebApp: { capable: true, title: "Seat Lock", statusBarStyle: "default" },
  formatDetection: { telephone: false },
};

export const viewport: Viewport = {
  themeColor: "#f2f4f1",
  width: "device-width",
  initialScale: 1,
  viewportFit: "cover", // lets us pad for the notch and home indicator ourselves
};

export default async function RootLayout({ children }: { children: React.ReactNode }) {
  const me = await getMe();
  const unread = me ? await api<{ unread: number }>("/me/notifications").then((r) => r.unread).catch(() => 0) : 0;
  return (
    <html lang="en-IN" className={overpass.variable}>
      <body className="min-h-dvh font-sans antialiased">
        <div className="mx-auto min-h-dvh max-w-md px-4" style={{ paddingTop: "var(--safe-top)" }}>
          {children}
        </div>
        <TabBar unread={unread} />
        <RegisterServiceWorker />
      </body>
    </html>
  );
}
