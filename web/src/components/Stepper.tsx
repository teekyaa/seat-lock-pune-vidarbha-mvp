import { CheckIcon } from "./icons";

const STEPS = [
  { key: "requested", label: "Requested" },
  { key: "accepted", label: "Accepted" },
  { key: "advance_claimed", label: "Paid" },
  { key: "confirmed", label: "Locked" },
  { key: "completed", label: "Done" },
];

/** Where a booking is in the happy path. Exits (cancelled, expired) show as a banner instead. */
export function Stepper({ status }: { status: string }) {
  const at = STEPS.findIndex((s) => s.key === status);
  if (at < 0) return null;
  return (
    <ol className="grid grid-cols-5 gap-1" aria-label="Booking progress">
      {STEPS.map((s, i) => {
        const done = i < at || status === "completed";
        const current = i === at && status !== "completed";
        return (
          <li key={s.key} className="flex flex-col items-center gap-1.5 text-center" aria-current={current ? "step" : undefined}>
            <span
              className={`grid h-7 w-7 place-items-center rounded-full text-xs font-bold ${
                done ? "bg-brand text-white" : current ? "bg-mile text-ink ring-4 ring-mile/30" : "bg-line text-muted"
              }`}
            >
              {done ? <CheckIcon /> : i + 1}
            </span>
            <span className={`text-[11px] font-semibold leading-tight ${current ? "text-ink" : "text-muted"}`}>{s.label}</span>
          </li>
        );
      })}
    </ol>
  );
}
