/** Large title for top-level tabs, as on iOS; reads as a normal heading on Android. */
export function PageHeader({ title, subtitle, trailing }: { title: string; subtitle?: string; trailing?: React.ReactNode }) {
  return (
    <header className="flex items-end justify-between gap-3 pb-4 pt-6">
      <div>
        <h1 className="text-[28px] font-extrabold leading-tight tracking-tight">{title}</h1>
        {subtitle && <p className="mt-1 text-base text-muted">{subtitle}</p>}
      </div>
      {trailing}
    </header>
  );
}
