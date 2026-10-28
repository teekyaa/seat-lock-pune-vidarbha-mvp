"use client";

import { useRouter, useSearchParams } from "next/navigation";
import { Suspense, useState } from "react";
import { call } from "@/lib/client";

function LoginForm() {
  const router = useRouter();
  const next = useSearchParams().get("next") || "/";
  const [phone, setPhone] = useState("");
  const [code, setCode] = useState("");
  const [sentTo, setSentTo] = useState<string | null>(null);
  const [devCode, setDevCode] = useState<string | null>(null);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  async function requestCode(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError("");
    try {
      const r = await call<{ phone: string; debug_code?: string }>("/auth/otp/request", "POST", { phone });
      setSentTo(r.phone);
      setDevCode(r.debug_code ?? null);
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setBusy(false);
    }
  }

  async function verify(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError("");
    const res = await fetch("/session", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ phone: sentTo, code }),
    });
    const data = await res.json().catch(() => ({}));
    setBusy(false);
    if (!res.ok) return setError(data.detail ?? "That didn't work. Try again.");
    router.push(data.user.profile_complete ? next : `/me?next=${encodeURIComponent(next)}`);
    router.refresh();
  }

  return (
    <div className="mx-auto max-w-sm space-y-4">
      <h1 className="text-2xl font-bold">Sign in with your phone</h1>
      {!sentTo ? (
        <form onSubmit={requestCode} className="card space-y-3">
          <label className="label" htmlFor="phone">Mobile number</label>
          <div className="flex items-center gap-2">
            <span className="rounded-xl border border-line bg-paper px-3 py-2.5 text-base">+91</span>
            <input id="phone" className="field" inputMode="numeric" autoComplete="tel-national" placeholder="98765 43210"
              value={phone} onChange={(e) => setPhone(e.target.value)} required />
          </div>
          <p className="hint">We&apos;ll send a 6 digit code by SMS. Your number stays private until a seat is confirmed.</p>
          <button className="btn-primary w-full" disabled={busy}>{busy ? "Sending" : "Send code"}</button>
        </form>
      ) : (
        <form onSubmit={verify} className="card space-y-3">
          <label className="label" htmlFor="code">Code sent to {sentTo}</label>
          <input id="code" className="field tracking-[0.4em]" inputMode="numeric" autoComplete="one-time-code" maxLength={6}
            value={code} onChange={(e) => setCode(e.target.value.replace(/\D/g, ""))} required autoFocus />
          {devCode && <p className="hint">Development build: your code is {devCode}.</p>}
          <button className="btn-primary w-full" disabled={busy || code.length !== 6}>{busy ? "Checking" : "Sign in"}</button>
          <button type="button" className="btn-secondary w-full" onClick={() => { setSentTo(null); setCode(""); }}>
            Use a different number
          </button>
        </form>
      )}
      {error && <p className="text-sm text-danger" role="alert">{error}</p>}
    </div>
  );
}

export default function LoginPage() {
  return (
    <Suspense>
      <LoginForm />
    </Suspense>
  );
}
