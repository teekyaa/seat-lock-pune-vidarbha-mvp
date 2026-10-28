import type { Reliability as Record } from "@/lib/types";

export function Reliability({ record, compact = false }: { record: Record; compact?: boolean }) {
  const late = record.passenger_late_cancellations + record.driver_late_cancellations;
  const flags = [
    late && `${late} late cancellation${late > 1 ? "s" : ""}`,
    record.no_shows && `${record.no_shows} no-show${record.no_shows > 1 ? "s" : ""}`,
    record.open_refund_disputes && `${record.open_refund_disputes} refund overdue`,
  ].filter(Boolean) as string[];

  if (compact) {
    return (
      <span className="text-xs text-muted">
        {record.completed_trips} trip{record.completed_trips === 1 ? "" : "s"}
        {flags.length > 0 && <span className="text-warn"> · {flags.join(" · ")}</span>}
      </span>
    );
  }
  const rows: [string, number][] = [
    ["Completed trips", record.completed_trips],
    ["Late cancellations as passenger", record.passenger_late_cancellations],
    ["Early cancellations as passenger", record.passenger_early_cancellations],
    ["Late cancellations as driver", record.driver_late_cancellations],
    ["Early cancellations as driver", record.driver_early_cancellations],
    ["Departure moved after confirming", record.driver_changes],
    ["No-shows", record.no_shows],
    ["Refunds overdue right now", record.open_refund_disputes],
  ];
  return (
    <dl className="grid grid-cols-2 gap-2 text-sm">
      {rows.map(([label, n]) => (
        <div key={label} className="rounded-xl bg-paper p-3">
          <dt className="text-xs text-muted">{label}</dt>
          <dd className={`text-lg font-bold ${n && label !== "Completed trips" ? "text-warn" : ""}`}>{n}</dd>
        </div>
      ))}
    </dl>
  );
}
