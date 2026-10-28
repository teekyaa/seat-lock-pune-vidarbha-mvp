import type { Reliability as Record } from "@/lib/types";

export function Reliability({ record }: { record: Record }) {
  const rows: [string, number, boolean][] = [
    ["Completed trips", record.completed_trips, false],
    ["Late cancellations as passenger", record.passenger_late_cancellations, true],
    ["Early cancellations as passenger", record.passenger_early_cancellations, false],
    ["Late cancellations as driver", record.driver_late_cancellations, true],
    ["Early cancellations as driver", record.driver_early_cancellations, false],
    ["Moved departure after confirming", record.driver_changes, true],
    ["No-shows", record.no_shows, true],
    ["Refunds overdue right now", record.open_refund_disputes, true],
  ];
  const [headline, ...rest] = rows;
  return (
    <div>
      <p className="text-4xl font-extrabold tabular-nums">{headline[1]}</p>
      <p className="text-sm text-muted">{headline[0]}</p>
      <dl className="mt-4 divide-y divide-line border-t border-line">
        {rest.map(([label, n, bad]) => (
          <div key={label} className="flex min-h-11 items-center justify-between gap-3 text-sm">
            <dt>{label}</dt>
            <dd className={`font-bold tabular-nums ${bad && n > 0 ? "text-warn" : "text-muted"}`}>{n}</dd>
          </div>
        ))}
      </dl>
    </div>
  );
}
