"use client";

import { useEffect, useState } from "react";
import { call } from "@/lib/client";

function urlBase64ToUint8Array(base64: string) {
  const padding = "=".repeat((4 - (base64.length % 4)) % 4);
  const raw = atob((base64 + padding).replace(/-/g, "+").replace(/_/g, "/"));
  return Uint8Array.from(raw, (c) => c.charCodeAt(0));
}

export function PushToggle() {
  const [state, setState] = useState<"unsupported" | "off" | "on" | "blocked" | "unconfigured">("off");
  const [error, setError] = useState("");

  useEffect(() => {
    if (!("serviceWorker" in navigator) || !("PushManager" in window)) return setState("unsupported");
    if (Notification.permission === "denied") return setState("blocked");
    navigator.serviceWorker.ready.then(async (reg) => setState((await reg.pushManager.getSubscription()) ? "on" : "off"));
  }, []);

  async function enable() {
    setError("");
    try {
      const { public_key } = await call<{ public_key: string }>("/push/key");
      if (!public_key) return setState("unconfigured");
      const reg = await navigator.serviceWorker.ready;
      const sub = await reg.pushManager.subscribe({ userVisibleOnly: true, applicationServerKey: urlBase64ToUint8Array(public_key) });
      await call("/push/subscriptions", "POST", sub.toJSON());
      setState("on");
    } catch (err) {
      setError(Notification.permission === "denied" ? "Notifications are blocked in your browser settings." : (err as Error).message);
    }
  }

  async function disable() {
    const reg = await navigator.serviceWorker.ready;
    const sub = await reg.pushManager.getSubscription();
    if (sub) {
      await call("/push/subscriptions", "DELETE", { endpoint: sub.endpoint }).catch(() => {});
      await sub.unsubscribe();
    }
    setState("off");
  }

  const text = {
    unsupported: "This browser can't show reminders. Add an email above instead, or install Seat Lock to your home screen.",
    blocked: "Notifications are blocked for this site in your browser settings.",
    unconfigured: "Phone reminders are not switched on for this server yet.",
    on: "Reminders are on for this phone.",
    off: "Get reconfirmation and pickup reminders on this phone.",
  }[state];

  return (
    <div className="space-y-2 text-sm">
      <p className="text-muted">{text}</p>
      {state === "off" && <button className="btn-secondary" onClick={enable}>Turn on reminders</button>}
      {state === "on" && <button className="btn-secondary" onClick={disable}>Turn off</button>}
      {error && <p className="text-danger">{error}</p>}
    </div>
  );
}
