"use client";

import { useEffect } from "react";
import { call } from "@/lib/client";

/** Marks everything read once the inbox has been seen. */
export function MarkRead() {
  useEffect(() => {
    call("/me/notifications", "POST").catch(() => {});
  }, []);
  return null;
}
