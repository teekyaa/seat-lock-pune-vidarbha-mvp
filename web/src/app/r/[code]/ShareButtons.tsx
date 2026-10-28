"use client";

import { useState } from "react";

export function ShareButtons({ url, text }: { url: string; text: string }) {
  const [copied, setCopied] = useState(false);
  return (
    <div className="flex gap-2">
      <a className="btn-primary flex-1 bg-[#128c4b] hover:bg-[#0e6f3b]" target="_blank" rel="noopener noreferrer"
        href={`https://wa.me/?text=${encodeURIComponent(`${text}\n${url}`)}`}>
        Share on WhatsApp
      </a>
      <button className="btn-secondary" onClick={async () => {
        await navigator.clipboard.writeText(url);
        setCopied(true);
        setTimeout(() => setCopied(false), 2000);
      }}>
        {copied ? "Copied" : "Copy link"}
      </button>
    </div>
  );
}
