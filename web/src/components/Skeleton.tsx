/** Placeholder shapes shown while a screen loads, so taps feel instant on slow networks. */
export function Skeleton({ rows = 3, header = true }: { rows?: number; header?: boolean }) {
  return (
    <div className="animate-pulse pt-6" aria-busy="true" aria-label="Loading">
      {header && <div className="mb-6 h-8 w-2/3 rounded-lg bg-line" />}
      <div className="space-y-3">
        {Array.from({ length: rows }, (_, i) => (
          <div key={i} className="card flex gap-3.5">
            <div className="h-16 w-16 rounded-t-[40%] bg-line" />
            <div className="flex-1 space-y-2 py-1">
              <div className="h-4 w-1/2 rounded bg-line" />
              <div className="h-3 w-3/4 rounded bg-line" />
              <div className="h-3 w-1/3 rounded bg-line" />
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
