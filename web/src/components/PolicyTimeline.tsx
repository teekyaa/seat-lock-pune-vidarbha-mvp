import type { Cutoffs } from "@/lib/types";

/**
 * What happens to the advance, as a timeline toward departure.
 * Exact IST timestamps, never "48 hours before" (hard rule 6).
 */
export function PolicyTimeline({ cutoffs, advance }: { cutoffs: Cutoffs; advance: number }) {
  const half = advance - Math.floor(advance / 2);
  const rows = [
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
        If someone takes your seat, or the driver cancels, you always get the full advance back.
      </p>
    </div>
  );
}
