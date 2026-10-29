/** Sticky bottom bar for the main action on pushed screens, sitting above the home indicator. */
export function ActionBar({ children }: { children: React.ReactNode }) {
  return (
    <div
      className="fixed inset-x-0 bottom-0 z-30 border-t border-line bg-surface/95 backdrop-blur-md"
      style={{ paddingBottom: "calc(12px + var(--safe-bottom))" }}
    >
      <div className="mx-auto max-w-md px-4 pt-3">{children}</div>
    </div>
  );
}
