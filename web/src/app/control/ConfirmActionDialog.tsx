"use client";

import { useEffect, useRef } from "react";

export function ConfirmActionDialog({ open, busy, onClose, children }: {
  open: boolean; busy: boolean; onClose: () => void; children: React.ReactNode;
}) {
  const ref = useRef<HTMLDialogElement>(null);
  useEffect(() => {
    const dialog = ref.current;
    if (!dialog) return;
    if (open && !dialog.open) dialog.showModal();
    if (!open && dialog.open) dialog.close();
  }, [open]);
  return <dialog ref={ref} aria-labelledby="confirm-action-title" className="control-card m-auto w-[min(94vw,32rem)] p-6 text-[var(--control-text)] backdrop:bg-black/60"
    onCancel={(event) => { event.preventDefault(); if (!busy) onClose(); }}>
    {children}
  </dialog>;
}
