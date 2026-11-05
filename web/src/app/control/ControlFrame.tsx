"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import type { FeatureFlag } from "@/lib/admin-server";

export function ControlFrame({ children }: { children: React.ReactNode }) {
  const path = usePathname();
  const router = useRouter();
  const [theme, setTheme] = useState<"light" | "dark">("light");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [flags, setFlags] = useState<FeatureFlag[] | null>(null);
  const [flagsUnavailable, setFlagsUnavailable] = useState(false);
  const isLogin = path === "/control/login";

  useEffect(() => {
    if (isLogin) return;
    let active = true;
    async function readFlags() {
      try {
        const response = await fetch("/admin-api/feature-flags?background=1", { cache: "no-store", signal: AbortSignal.timeout(10000) });
        if (!response.ok) throw new Error("Control status unavailable");
        const data = await response.json() as FeatureFlag[];
        if (active) { setFlags(data); setFlagsUnavailable(false); }
      } catch {
        if (active) setFlagsUnavailable(true);
      }
    }
    void readFlags();
    const timer = setInterval(() => { void readFlags(); }, 30000);
    const onChange = () => { void readFlags(); };
    window.addEventListener("admin-control-changed", onChange);
    return () => { active = false; clearInterval(timer); window.removeEventListener("admin-control-changed", onChange); };
  }, [isLogin]);

  async function logout() {
    setBusy(true);
    setError("");
    try {
      const response = await fetch("/admin-session", { method: "DELETE" });
      if (!response.ok) throw new Error("Could not sign out. Please try again.");
      router.replace("/control/login");
      router.refresh();
    } catch {
      setError("Could not sign out. Please try again.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="control-shell -mx-4 px-4 pb-10" data-theme={theme}>
      <header className="flex flex-wrap items-center justify-between gap-3 border-b py-4" style={{ borderColor: "var(--control-line)" }}>
        <Link href="/control" className="text-lg font-extrabold">Seat Lock <span className="control-muted font-semibold">/ Operations</span></Link>
        <div className="flex items-center gap-2">
          <button className="control-button text-sm" onClick={() => setTheme(theme === "light" ? "dark" : "light")}>
            {theme === "light" ? "Dark mode" : "Light mode"}
          </button>
          {!isLogin && <button className="control-button text-sm" disabled={busy} onClick={logout}>{busy ? "Signing out…" : "Sign out"}</button>}
        </div>
      </header>
      {error && <p role="alert" className="mt-4 rounded-xl bg-red-100 p-3 text-red-900">{error}</p>}
      {!isLogin && flagsUnavailable && <p role="alert" className="mt-4 rounded-xl bg-amber-100 p-3 text-sm text-amber-950">Control status is unavailable; refresh before taking action.</p>}
      {!isLogin && flags?.filter((flag) => !flag.value).map((flag) => <p key={flag.key} role="status" className="mt-4 rounded-xl bg-amber-100 p-3 text-sm text-amber-950">
        Paused: {flag.description} {flag.updated_by ? `Changed by ${flag.updated_by}.` : ""} {flag.updated_at ? `At ${new Intl.DateTimeFormat("en-IN", { timeZone: "Asia/Kolkata", dateStyle: "medium", timeStyle: "short" }).format(new Date(flag.updated_at))} IST.` : ""}
      </p>)}
      <main>{children}</main>
    </div>
  );
}
