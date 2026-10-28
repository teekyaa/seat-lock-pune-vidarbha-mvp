/**
 * The one memorable element: a Maharashtra highway milestone.
 * Yellow cap with the destination, white stone with the distance. Used for every route.
 */
export function RouteMark({ origin, destination, km, size = "md" }: {
  origin: string; destination: string; km?: number; size?: "sm" | "md" | "lg";
}) {
  const dims = {
    sm: { w: "w-16", cap: "text-[10px] py-1", body: "text-sm py-1.5" },
    md: { w: "w-20", cap: "text-[11px] py-1", body: "text-base py-2" },
    lg: { w: "w-28", cap: "text-sm py-1.5", body: "text-2xl py-3" },
  }[size];
  return (
    <div
      className={`${dims.w} shrink-0 self-start overflow-hidden rounded-t-[40%] bg-surface text-center ring-1 ring-ink/15`}
      role="img"
      aria-label={`${origin} to ${destination}${km ? `, ${km} km` : ""}`}
    >
      <div className={`bg-mile px-1 font-bold uppercase leading-none text-ink ${dims.cap} pt-2`}>{destination.slice(0, 9)}</div>
      <div className={`font-extrabold leading-none tabular-nums text-ink ${dims.body}`}>
        {km ?? "·"}
        {km && <span className="ml-0.5 text-[0.6em] font-bold">km</span>}
      </div>
    </div>
  );
}
