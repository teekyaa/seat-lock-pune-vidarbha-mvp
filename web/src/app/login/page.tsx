"use client";

import { useRouter, useSearchParams } from "next/navigation";
import { Suspense, useEffect, useRef, useState } from "react";
import { RouteMark } from "@/components/RouteMark";
import { TopBar } from "@/components/TopBar";
import { safeRedirect } from "@/lib/safe-redirect";

function formatWait(seconds: number) {
  return seconds >= 60 ? `${Math.floor(seconds / 60)}m ${String(seconds % 60).padStart(2, "0")}s` : `${seconds}s`;
}

function LoginForm() {
  const router = useRouter();
  const next = safeRedirect(useSearchParams().get("next"));
  const [phone, setPhone] = useState("");
  const [code, setCode] = useState("");
  const [sentTo, setSentTo] = useState<string | null>(null);
  const [devCode, setDevCode] = useState<string | null>(null);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [wait, setWait] = useState(0);
  const [channel, setChannel] = useState<"whatsapp" | "sms">("sms");
  const [smsAvailable, setSmsAvailable] = useState(false);
  const verifying = useRef(false);

  useEffect(() => {
    if (wait <= 0) return;
    const t = setTimeout(() => setWait(wait - 1), 1000);
    return () => clearTimeout(t);
  }, [wait]);

  async function requestCode(e?: React.FormEvent, via?: "sms") {
    e?.preventDefault();
    setBusy(true);
    setError("");
    try {
      const res = await fetch("/api/proxy/auth/otp/request", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(via ? { phone, channel: via } : { phone }),
      });
      const r = await res.json().catch(() => ({}));
      if (!res.ok) {
        // The server says how long to wait, including the exact end of any block.
        if (typeof r.retry_after === "number" && sentTo) setWait(Math.min(r.retry_after, 3600));
        return setError(r.detail ?? "We couldn't send a code. Please try again.");
      }
      setSentTo(r.phone);
      setChannel(r.channel === "whatsapp" ? "whatsapp" : "sms");
      setSmsAvailable(Boolean(r.sms_available));
      setDevCode(r.debug_code ?? null);
      setCode("");
      setWait(r.resend_after);
    } catch {
      setError("Could not connect. Please try again.");
    } finally {
      setBusy(false);
    }
  }

  async function verify(value: string) {
    if (verifying.current) return;
    verifying.current = true;
    setBusy(true);
    setError("");
    try {
    const res = await fetch("/session", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ phone: sentTo, code: value }),
    });
    const data = await res.json().catch(() => ({}));
    if (!res.ok) {
      setCode("");
      return setError(data.detail ?? "That didn't work. Try again.");
    }
    router.replace(data.user.profile_complete ? next : `/me?next=${encodeURIComponent(next)}`);
    router.refresh();
    } catch {
      setError("Could not connect. Please try again.");
    } finally {
      verifying.current = false;
      setBusy(false);
    }
  }

  const digits = phone.replace(/\D/g, "");

  return (
    <div className="pb-10">
      <TopBar title="" />
      <div className="flex items-center gap-4 pb-6 pt-2">
        <RouteMark origin="Pune" destination="Vidarbha" size="md" />
        <div>
          <h1 className="text-[28px] font-extrabold leading-tight tracking-tight">Seat Lock</h1>
          <p className="text-base text-muted">Carpools between Pune and Vidarbha, with seats that stay booked.</p>
        </div>
      </div>

      {!sentTo ? (
        <form onSubmit={requestCode} className="space-y-4">
          <div>
            <label className="label" htmlFor="phone">Your mobile number</label>
            <div className="flex items-stretch gap-2">
              <span className="grid min-h-14 place-items-center rounded-xl bg-line/70 px-4 text-lg font-bold">+91</span>
              <input id="phone" className="field min-h-14 text-lg font-bold tracking-wide" type="tel" inputMode="numeric" autoComplete="tel-national"
                placeholder="98765 43210" value={phone} maxLength={14} onChange={(e) => setPhone(e.target.value)} autoFocus required />
            </div>
            <p className="hint">We send a 6 digit code on WhatsApp, or by SMS. Your number stays private until a seat is confirmed.</p>
          </div>
          <button className="btn-primary w-full" disabled={busy || digits.length < 10}>{busy ? "Sending code" : "Send code"}</button>
        </form>
      ) : (
        <div className="space-y-4">
          <div>
            <label className="label" htmlFor="code">
              Enter the code sent to {sentTo} {channel === "whatsapp" ? "on WhatsApp" : "by SMS"}
            </label>
            <input id="code" className="field min-h-14 text-center text-2xl font-extrabold tracking-[0.5em]" inputMode="numeric"
              autoComplete="one-time-code" maxLength={6} value={code} autoFocus disabled={busy}
              onChange={(e) => {
                const v = e.target.value.replace(/\D/g, "").slice(0, 6);
                setCode(v);
                if (v.length === 6) verify(v); // SMS autofill on iOS and Android fills all six at once
              }} />
            {devCode && <p className="hint">Development build: the code is {devCode}.</p>}
          </div>
          <button className="btn-primary w-full" disabled={busy || code.length !== 6} onClick={() => verify(code)}>
            {busy ? "Checking" : "Sign in"}
          </button>
          <div className="flex justify-between text-sm font-semibold">
            <button className="min-h-11 text-brand" onClick={() => { setSentTo(null); setCode(""); setError(""); }}>Change number</button>
            <button className="min-h-11 text-brand disabled:text-muted" disabled={wait > 0 || busy} onClick={() => requestCode()}>
              {wait > 0 ? `Resend in ${formatWait(wait)}` : "Resend code"}
            </button>
          </div>
          {channel === "whatsapp" && smsAvailable && (
            <button className="btn-secondary w-full" disabled={wait > 0 || busy} onClick={() => requestCode(undefined, "sms")}>
              {wait > 0 ? `Not on WhatsApp? Send by SMS in ${formatWait(wait)}` : "Not on WhatsApp? Send by SMS"}
            </button>
          )}
        </div>
      )}
      {error && <p className="mt-4 rounded-xl bg-danger-wash p-3 text-sm text-danger" role="alert">{error}</p>}
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
