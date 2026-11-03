"use client";

import type { RouteStopInfo } from "@/lib/types";

function km(value: string) {
  const n = Number(value);
  return `${Number.isInteger(n) ? n : n.toFixed(1)} km`;
}

/**
 * The route as a vertical line of stops with distance from the start, like milestones along the road.
 * With `onToggle`, middle stops get a switch so the driver can choose where they stop.
 */
export function RouteDiagram({ stops, onToggle }: {
  stops: RouteStopInfo[]; onToggle?: (index: number, enabled: boolean) => void;
}) {
  return (
    <ol className="relative space-y-0" aria-label="Stops on this route">
      {stops.map((s, i) => {
        const end = i === 0 || i === stops.length - 1;
        const enabled = s.enabled !== false;
        return (
          <li key={`${s.name}-${i}`} className="relative flex min-h-14 items-center gap-3 pl-7">
            {i < stops.length - 1 && <span className="absolute left-[9px] top-1/2 h-full w-0.5 bg-ink/15" aria-hidden />}
            <span aria-hidden className={`absolute left-0 top-1/2 h-5 w-5 -translate-y-1/2 rounded-full ${
              end ? "bg-brand ring-4 ring-brand-wash" : enabled ? "border-[3px] border-brand bg-surface" : "border-2 border-line bg-paper"
            }`} />
            <span className="min-w-0 flex-1">
              <span className={`block font-bold ${enabled ? "" : "text-muted line-through"}`}>{s.name}</span>
              <span className="block text-xs text-muted tabular-nums">{i === 0 ? "Start" : km(s.km)}{!enabled && ", not stopping"}</span>
            </span>
            {onToggle && !end && (
              <label className="flex min-h-11 items-center gap-2 text-sm font-semibold">
                <input type="checkbox" className="h-5 w-5 accent-brand" checked={enabled} aria-label={`Stop at ${s.name}`}
                  onChange={(e) => onToggle(i, e.target.checked)} />
                Stop
              </label>
            )}
          </li>
        );
      })}
    </ol>
  );
}
