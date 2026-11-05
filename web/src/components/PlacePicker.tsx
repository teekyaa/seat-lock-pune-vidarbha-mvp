"use client";

import { useEffect, useState } from "react";
import type { Place } from "@/lib/types";
import { Combobox } from "./Combobox";

const REGION: Record<Place["region"], string> = { west: "Pune side", marathwada: "Marathwada", vidarbha: "Vidarbha" };

/** Pick a town from our own place list. Matches names and old names such as Aurangabad. */
export function PlacePicker({ id, label, places, value, onChange, exclude }: {
  id: string; label: string; places: Place[]; value: Place | null; onChange: (p: Place | null) => void; exclude?: number;
}) {
  const [text, setText] = useState(value?.name ?? "");
  // Follow the chosen place, but never wipe what someone is typing when the choice is cleared.
  useEffect(() => { if (value) setText(value.name); }, [value]);

  const q = text.trim().toLowerCase();
  const matches = places
    .filter((p) => p.id !== exclude)
    .filter((p) => !q || value?.name === text || [p.name, ...p.aliases].some((n) => n.toLowerCase().includes(q)));

  return (
    <Combobox
      id={id}
      label={label}
      placeholder="Type a town"
      value={text}
      onInput={(t) => { setText(t); if (value && t !== value.name) onChange(null); }}
      options={matches.map((p) => ({
        key: String(p.id), label: p.name,
        detail: [REGION[p.region], p.aliases.length ? `also ${p.aliases.join(", ")}` : ""].filter(Boolean).join(", "),
      }))}
      onSelect={(o) => onChange(places.find((p) => String(p.id) === o.key) ?? null)}
      emptyText="Not on our routes yet. Pick the nearest town."
    />
  );
}
