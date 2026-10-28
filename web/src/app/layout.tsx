import type { Metadata, Viewport } from "next";
import { Plus_Jakarta_Sans } from "next/font/google";
import Link from "next/link";
import { RegisterServiceWorker } from "@/components/RegisterServiceWorker";
import { getMe } from "@/lib/server";
import "./globals.css";

const jakarta = Plus_Jakarta_Sans({ variable: "--font-jakarta", subsets: ["latin"] });

export const metadata: Metadata = {
  metadataBase: new URL(process.env.NEXT_PUBLIC_SITE_URL ?? "http://localhost:3000"),
  title: { default: "Seat Lock: Pune to Vidarbha carpools", template: "%s · Seat Lock" },
  description: "Share the cost of the drive between Pune and Nagpur, Wardha or Chandrapur. Every seat is locked with a small UPI advance.",
  applicationName: "Seat Lock",
};

export const viewport: Viewport = { themeColor: "#1f7a5e", width: "device-width", initialScale: 1 };

export default async function RootLayout({ children }: { children: React.ReactNode }) {
  const me = await getMe();
  return (
    <html lang="en-IN" className={jakarta.variable}>
      <body className="min-h-screen font-sans antialiased">
        <header className="sticky top-0 z-10 border-b border-line bg-white/90 backdrop-blur">
          <div className="mx-auto flex h-14 max-w-3xl items-center gap-4 px-4">
            <Link href="/" className="flex items-center gap-2 font-bold tracking-tight" aria-label="Seat Lock home">
              <span className="grid h-8 w-8 place-items-center rounded-lg bg-brand text-white" aria-hidden>
                <svg viewBox="0 0 24 24" className="h-5 w-5" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                  <rect x="5" y="11" width="14" height="9" rx="2" />
                  <path d="M8 11V8a4 4 0 0 1 8 0v3" />
                </svg>
              </span>
              <span className={me ? "hidden sm:inline" : ""}>Seat Lock</span>
            </Link>
            <nav className="ml-auto flex items-center gap-1 text-sm font-medium">
              <Link href="/" className="rounded-lg px-2 py-1.5 hover:bg-paper">Find</Link>
              <Link href="/rides/new" className="rounded-lg px-2 py-1.5 hover:bg-paper">Offer</Link>
              {me ? (
                <>
                  <Link href="/bookings" className="rounded-lg px-2 py-1.5 hover:bg-paper">Trips</Link>
                  <Link href="/inbox" className="rounded-lg px-2 py-1.5 hover:bg-paper">Inbox</Link>
                  <Link href="/me" className="ml-1 grid h-8 w-8 place-items-center rounded-full bg-brand-wash text-xs font-bold text-brand" aria-label="Your profile">
                    {(me.name || "?").slice(0, 1).toUpperCase()}
                  </Link>
                </>
              ) : (
                <Link href="/login" className="btn-primary ml-1 min-h-9 px-3">Sign in</Link>
              )}
            </nav>
          </div>
        </header>
        {me && !me.profile_complete && (
          <div className="bg-warn-wash px-4 py-2 text-center text-sm text-warn">
            Your profile is not finished yet. <Link href="/me" className="font-semibold underline">Finish it</Link> to post or book.
          </div>
        )}
        <main className="mx-auto max-w-3xl px-4 pb-24 pt-5">{children}</main>
        <footer className="mx-auto max-w-3xl px-4 pb-10 text-xs text-muted">
          Seat Lock never holds your money. Advances and refunds go straight between people over UPI. Fares are cost-sharing only.
        </footer>
        <RegisterServiceWorker />
      </body>
    </html>
  );
}
