"use client";

import { useRouter } from "next/navigation";
import { BackIcon } from "./icons";

/** Header for pushed screens: back button, centred title, optional trailing action. */
export function TopBar({ title, fallback = "/", trailing }: { title: string; fallback?: string; trailing?: React.ReactNode }) {
  const router = useRouter();
  return (
    <header
      className="sticky top-0 z-20 -mx-4 mb-4 grid grid-cols-[48px_1fr_48px] items-center border-b border-line bg-paper/95 px-1 backdrop-blur-md"
      style={{ paddingTop: "var(--safe-top)" }}
    >
      <button
        type="button"
        aria-label="Back"
        className="grid h-12 w-12 place-items-center rounded-full text-ink active:bg-line/60"
        onClick={() => (window.history.length > 1 ? router.back() : router.push(fallback))}
      >
        <BackIcon />
      </button>
      <h1 className="truncate text-center text-base font-bold">{title}</h1>
      <div className="flex justify-end">{trailing}</div>
    </header>
  );
}
