"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";
import type { components } from "@/lib/admin-api.generated";

type LoginRequest = components["schemas"]["AdminLoginRequest"];

export default function AdminLogin() {
  const router = useRouter();
  const [form, setForm] = useState<LoginRequest>({ email: "", password: "", code: "" });
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  async function submit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (busy) return;
    setBusy(true);
    setError("");
    try {
      const response = await fetch("/admin-session", {
        method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(form),
      });
      if (!response.ok) {
        const data: unknown = await response.json();
        const detail = data && typeof data === "object" && "detail" in data && typeof data.detail === "string"
          ? data.detail : "Unable to sign in.";
        throw new Error(detail);
      }
      setForm({ email: "", password: "", code: "" });
      router.replace("/control");
      router.refresh();
    } catch (failure) {
      setError(failure instanceof Error ? failure.message : "Unable to sign in.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <section className="mx-auto max-w-md py-12">
      <p className="text-sm font-bold uppercase tracking-wider text-green-700">Seat Lock operations</p>
      <h1 className="mt-2 text-3xl font-extrabold">Admin sign in</h1>
      <p className="control-muted mt-2">Use your separate administrator account and authenticator code.</p>
      <form onSubmit={submit} className="control-card mt-6 space-y-5 p-6">
        <label className="block font-semibold">Email
          <input className="control-input mt-1" type="email" autoComplete="username" required maxLength={254}
            value={form.email} onChange={(event) => setForm({ ...form, email: event.target.value })} />
        </label>
        <label className="block font-semibold">Password
          <input className="control-input mt-1" type="password" autoComplete="current-password" required maxLength={1024}
            value={form.password} onChange={(event) => setForm({ ...form, password: event.target.value })} />
        </label>
        <label className="block font-semibold">Authenticator code
          <input className="control-input mt-1" type="text" inputMode="numeric" autoComplete="one-time-code" required
            pattern="[0-9]{6}" maxLength={6} value={form.code}
            onChange={(event) => setForm({ ...form, code: event.target.value.replace(/\D/g, "").slice(0, 6) })} />
        </label>
        {error && <p role="alert" className="rounded-xl bg-red-100 p-3 text-sm text-red-900">{error}</p>}
        <button disabled={busy} className="w-full rounded-xl bg-green-800 p-3 font-bold text-white disabled:opacity-50">
          {busy ? "Signing in…" : "Sign in"}
        </button>
      </form>
    </section>
  );
}
