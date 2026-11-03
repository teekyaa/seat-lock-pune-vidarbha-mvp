"use client";

import { useEffect, useRef, useState } from "react";
import { call } from "@/lib/client";
import type { PickupResult } from "@/lib/types";
import { Combobox } from "./Combobox";

/**
 * Exact pickup point, searched with Mappls through our API (the key never reaches the browser).
 * If Mappls is off or down, it quietly becomes a plain text field so posting is never blocked.
 */
export function PickupSearch({ id, label, nearPlaceId, value, onChange }: {
  id: string; label: string; nearPlaceId?: number; value: PickupResult; onChange: (v: PickupResult) => void;
}) {
  const [results, setResults] = useState<PickupResult[]>([]);
  const [loading, setLoading] = useState(false);
  // null until we know whether place search is switched on for this server.
  const [available, setAvailable] = useState<boolean | null>(null);
  const timer = useRef<ReturnType<typeof setTimeout> | null>(null);

  useEffect(() => {
    let live = true;
    call<{ available: boolean }>("/places/search?q=")
      .then((r) => live && setAvailable(r.available))
      .catch(() => live && setAvailable(false));
    return () => { live = false; if (timer.current) clearTimeout(timer.current); };
  }, []);

  function search(text: string) {
    onChange({ name: text, address: "", eloc: "" });
    if (timer.current) clearTimeout(timer.current);
    if (available !== true || text.trim().length < 2) { setResults([]); return; }
    timer.current = setTimeout(async () => {
      setLoading(true);
      try {
        const params = new URLSearchParams({ q: text.trim() });
        if (nearPlaceId) params.set("near", String(nearPlaceId));
        const r = await call<{ available: boolean; results: PickupResult[] }>(`/places/search?${params}`);
        setAvailable(r.available);
        setResults(r.results);
      } catch {
        setResults([]);
      } finally {
        setLoading(false);
      }
    }, 300);
  }

  return (
    <Combobox
      id={id}
      label={label}
      placeholder={available === false ? "e.g. Shivajinagar bus stand" : "Search a landmark, e.g. Shivajinagar bus stand"}
      value={value.name}
      onInput={search}
      loading={loading}
      options={results.map((r, i) => ({ key: r.eloc || String(i), label: r.name, detail: r.address }))}
      onSelect={(o) => {
        const hit = results.find((r, i) => (r.eloc || String(i)) === o.key);
        if (hit) onChange(hit);
      }}
      emptyText={available === true ? "No matches. Keep typing, or use what you typed." : undefined}
      hint={value.address ? value.address : available === false ? "Type the spot people should come to." : "Pick from the list for the exact spot."}
    />
  );
}
