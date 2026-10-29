"use client";

import { useEffect, useRef } from "react";

/**
 * Bottom sheet built on <dialog>: focus trap, Esc to close and the back gesture handled by the browser.
 * Replaces window.confirm, which looks broken on mobile and can't explain consequences well.
 */
export function Sheet({ open, onClose, title, children }: {
  open: boolean; onClose: () => void; title: string; children: React.ReactNode;
}) {
  const ref = useRef<HTMLDialogElement>(null);

  useEffect(() => {
    const d = ref.current;
    if (!d) return;
    if (open && !d.open) d.showModal();
    if (!open && d.open) d.close();
  }, [open]);

  return (
    <dialog
      ref={ref}
      onClose={onClose}
      onClick={(e) => { if (e.target === ref.current) onClose(); }}
      className="m-0 mt-auto w-full max-w-none bg-transparent p-0 backdrop:animate-fade backdrop:bg-ink/45 sm:mx-auto sm:max-w-md"
    >
      <div
        className="animate-sheet max-h-[88dvh] overflow-y-auto rounded-t-3xl bg-surface px-5 pt-2"
        style={{ paddingBottom: "calc(20px + var(--safe-bottom))" }}
      >
        <div className="mx-auto mb-3 h-1.5 w-10 rounded-full bg-line" aria-hidden />
        <h2 className="mb-3 text-xl font-bold">{title}</h2>
        {open && children}
      </div>
    </dialog>
  );
}

/** A confirm sheet for consequential actions. */
export function ConfirmSheet({ open, onClose, title, body, confirmLabel, danger, busy, onConfirm }: {
  open: boolean; onClose: () => void; title: string; body: React.ReactNode; confirmLabel: string;
  danger?: boolean; busy?: boolean; onConfirm: () => void;
}) {
  return (
    <Sheet open={open} onClose={onClose} title={title}>
      <div className="space-y-4 text-base text-ink">{body}</div>
      <div className="mt-6 grid gap-2">
        <button className={danger ? "btn bg-danger text-white" : "btn-primary"} disabled={busy} onClick={onConfirm}>
          {busy ? "Working" : confirmLabel}
        </button>
        <button className="btn-ghost" onClick={onClose}>Not now</button>
      </div>
    </Sheet>
  );
}
