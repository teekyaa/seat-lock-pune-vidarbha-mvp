import type { Cutoffs } from "@/lib/types";

/**
 * What happens if plans change, as a timeline toward departure.
 * Exact IST timestamps, never "48 hours before" (hard rule 6).
 * Rides without an advance have nothing to refund, so only the record is at stake.
 */
export function PolicyTimeline({ cutoffs, advance }: { cutoffs: Cutoffs; advance: number }) {
  const noAdvance = advance === 0;
  const half = advance - Math.floor(advance / 2);
  const rows = noAdvance
    ? [
        { tone: "bg-brand", when: `Before ${cutoffs.full_refund_until.ist}`, text: "Cancel and it counts as an early cancellation." },
        { tone: "bg-danger", when: "After that", text: "Cancelling or not turning up shows as late on your public record." },
      ]
    : [
        { tone: "bg-brand", when: `Before ${cutoffs.full_refund_until.ist}`, text: `Cancel and you get all ₹${advance} back.` },
        { tone: "bg-mile", when: `Until ${cutoffs.full_penalty_from.ist}`, text: `Cancel and you get ₹${half} back.` },
        { tone: "bg-danger", when: "After that", text: "If you cancel or don't turn up, the driver keeps the advance." },
      ];
  return (
    <div>
      <ol className="relative space-y-4 pl-6">
        <span className="absolute bottom-2 left-[5px] top-2 w-0.5 bg-line" aria-hidden />
        {rows.map((r) => (
          <li key={r.when} className="relative">
            <span className={`absolute -left-6 top-1 h-3 w-3 rounded-full ring-4 ring-surface ${r.tone}`} aria-hidden />
            <p className="text-sm font-bold">{r.when}</p>
            <p className="text-sm text-muted">{r.text}</p>
          </li>
        ))}
      </ol>
      <p className="mt-4 rounded-xl bg-brand-wash p-3 text-sm text-brand">
        {noAdvance
          ? "There's no advance on this ride, so no money changes hands until the trip."
          : "If someone takes your seat, or the driver cancels, you always get the full advance back."}
      </p>
    </div>
  );
}
