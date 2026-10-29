"use client";

import { useState } from "react";
import { ShareIcon } from "@/components/icons";

/** Opens the phone's own share sheet (WhatsApp is one tap away there); falls back to WhatsApp web. */
export function ShareButton({ url, text, variant = "icon" }: { url: string; text: string; variant?: "icon" | "button" }) {
  const [copied, setCopied] = useState(false);

  async function share() {
    if (navigator.share) {
      try {
        await navigator.share({ title: "Seat Lock ride", text, url });
        return;
      } catch (e) {
        if ((e as Error).name === "AbortError") return;
      }
    }
    window.open(`https://wa.me/?text=${encodeURIComponent(`${text}\n${url}`)}`, "_blank", "noopener");
  }

  async function copy() {
    await navigator.clipboard.writeText(url);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  }

  if (variant === "icon") {
    return (
      <button type="button" aria-label="Share this ride" onClick={share}
        className="grid h-12 w-12 place-items-center rounded-full text-ink active:bg-line/60">
        <ShareIcon className="h-[22px] w-[22px]" />
      </button>
    );
  }
  return (
    <div className="grid grid-cols-[1fr_auto] gap-2">
      <button type="button" className="btn-primary" onClick={share}><ShareIcon /> Share ride</button>
      <button type="button" className="btn-secondary" onClick={copy}>{copied ? "Copied" : "Copy link"}</button>
    </div>
  );
}
