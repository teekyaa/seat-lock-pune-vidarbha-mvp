"use client";

import { useEffect, useId, useRef, useState } from "react";

export type ComboOption = { key: string; label: string; detail?: string };

/**
 * Accessible search-as-you-type dropdown (WAI-ARIA combobox pattern). Works for a local list
 * (places) and for async results (Mappls). Typing never gets blocked: the text stays editable.
 */
export function Combobox({ id, label, placeholder, value, onInput, options, onSelect, hint, loading, emptyText }: {
  id: string;
  label: string;
  placeholder?: string;
  value: string;
  onInput: (text: string) => void;
  options: ComboOption[];
  onSelect: (option: ComboOption) => void;
  hint?: React.ReactNode;
  loading?: boolean;
  emptyText?: string;
}) {
  const listId = useId();
  const [open, setOpen] = useState(false);
  const [active, setActive] = useState(0);
  const wrap = useRef<HTMLDivElement>(null);

  useEffect(() => setActive(0), [options]);
  useEffect(() => {
    const close = (e: PointerEvent) => { if (!wrap.current?.contains(e.target as Node)) setOpen(false); };
    document.addEventListener("pointerdown", close);
    return () => document.removeEventListener("pointerdown", close);
  }, []);

  function choose(option: ComboOption) {
    onSelect(option);
    setOpen(false);
  }

  const showList = open && (options.length > 0 || loading || Boolean(emptyText && value.trim().length >= 2));

  return (
    <div ref={wrap} className="relative">
      <label className="label" htmlFor={id} id={`${id}-label`}>{label}</label>
      <input
        id={id}
        aria-labelledby={`${id}-label`}
        className="field"
        role="combobox"
        aria-expanded={showList}
        aria-controls={listId}
        aria-autocomplete="list"
        aria-activedescendant={showList && options[active] ? `${listId}-${active}` : undefined}
        autoComplete="off"
        placeholder={placeholder}
        value={value}
        onFocus={() => setOpen(true)}
        onBlur={() => setOpen(false)}
        onChange={(e) => { onInput(e.target.value); setOpen(true); }}
        onKeyDown={(e) => {
          if (e.key === "ArrowDown") { e.preventDefault(); setOpen(true); setActive((a) => Math.min(a + 1, options.length - 1)); }
          else if (e.key === "ArrowUp") { e.preventDefault(); setActive((a) => Math.max(a - 1, 0)); }
          else if (e.key === "Enter" && showList && options[active]) { e.preventDefault(); choose(options[active]); }
          else if (e.key === "Escape") setOpen(false);
        }}
      />
      {hint && <p className="hint">{hint}</p>}
      {showList && (
        <ul id={listId} role="listbox" aria-label={label}
          className="absolute inset-x-0 top-full z-20 mt-1 max-h-72 overflow-y-auto rounded-xl bg-surface py-1 shadow-lg ring-1 ring-line">
          {loading && <li className="px-4 py-3 text-sm text-muted">Searching</li>}
          {!loading && options.length === 0 && emptyText && <li className="px-4 py-3 text-sm text-muted">{emptyText}</li>}
          {options.map((o, i) => (
            <li key={o.key} id={`${listId}-${i}`} role="option" aria-selected={i === active}
              className={`min-h-12 cursor-pointer px-4 py-2.5 ${i === active ? "bg-brand-wash" : ""}`}
              onPointerDown={(e) => e.preventDefault()}
              onClick={() => choose(o)}
              onPointerEnter={() => setActive(i)}>
              <span className="block font-semibold">{o.label}</span>
              {o.detail && <span className="block text-sm text-muted">{o.detail}</span>}
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
