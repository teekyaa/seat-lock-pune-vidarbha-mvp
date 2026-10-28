// Small hand-drawn icon set (24px grid, 2px stroke) so we don't pull in an icon dependency.
type P = { className?: string };
const base = {
  fill: "none",
  stroke: "currentColor",
  strokeWidth: 2,
  strokeLinecap: "round" as const,
  strokeLinejoin: "round" as const,
  viewBox: "0 0 24 24",
  "aria-hidden": true,
};

export const SearchIcon = ({ className = "h-6 w-6" }: P) => (
  <svg {...base} className={className}><circle cx="11" cy="11" r="7" /><path d="m20 20-3.5-3.5" /></svg>
);
export const TicketIcon = ({ className = "h-6 w-6" }: P) => (
  <svg {...base} className={className}><rect x="5" y="11" width="14" height="9" rx="2" /><path d="M8 11V8a4 4 0 0 1 8 0v3" /></svg>
);
export const PlusIcon = ({ className = "h-6 w-6" }: P) => (
  <svg {...base} className={className}><path d="M12 5v14M5 12h14" /></svg>
);
export const BellIcon = ({ className = "h-6 w-6" }: P) => (
  <svg {...base} className={className}><path d="M6 8a6 6 0 1 1 12 0c0 7 3 8 3 8H3s3-1 3-8" /><path d="M10.3 21a1.9 1.9 0 0 0 3.4 0" /></svg>
);
export const UserIcon = ({ className = "h-6 w-6" }: P) => (
  <svg {...base} className={className}><circle cx="12" cy="8" r="4" /><path d="M4 21a8 8 0 0 1 16 0" /></svg>
);
export const BackIcon = ({ className = "h-6 w-6" }: P) => (
  <svg {...base} className={className}><path d="m15 18-6-6 6-6" /></svg>
);
export const ChevronIcon = ({ className = "h-5 w-5" }: P) => (
  <svg {...base} className={className}><path d="m9 18 6-6-6-6" /></svg>
);
export const SwapIcon = ({ className = "h-5 w-5" }: P) => (
  <svg {...base} className={className}><path d="M7 4v16M7 4 3 8M7 4l4 4M17 20V4M17 20l-4-4M17 20l4-4" /></svg>
);
export const PhoneIcon = ({ className = "h-5 w-5" }: P) => (
  <svg {...base} className={className}><path d="M22 16.9v3a2 2 0 0 1-2.2 2 19.8 19.8 0 0 1-8.6-3.1 19.5 19.5 0 0 1-6-6A19.8 19.8 0 0 1 2.1 4.2 2 2 0 0 1 4.1 2h3a2 2 0 0 1 2 1.7c.1.9.4 1.8.7 2.7a2 2 0 0 1-.5 2.1L8 9.8a16 16 0 0 0 6 6l1.3-1.3a2 2 0 0 1 2.1-.4c.9.3 1.8.6 2.7.7a2 2 0 0 1 1.7 2Z" /></svg>
);
export const ShareIcon = ({ className = "h-5 w-5" }: P) => (
  <svg {...base} className={className}><path d="M4 12v7a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2v-7M16 6l-4-4-4 4M12 2v13" /></svg>
);
export const CheckIcon = ({ className = "h-4 w-4" }: P) => (
  <svg {...base} className={className}><path d="M20 6 9 17l-5-5" /></svg>
);
export const MoreIcon = ({ className = "h-6 w-6" }: P) => (
  <svg {...base} className={className}><circle cx="5" cy="12" r="1" /><circle cx="12" cy="12" r="1" /><circle cx="19" cy="12" r="1" /></svg>
);
export const CarIcon = ({ className = "h-5 w-5" }: P) => (
  <svg {...base} className={className}><path d="M5 17h14M5 17v2M19 17v2M3 13l2-6h14l2 6v4H3z" /><circle cx="7.5" cy="14" r=".5" /><circle cx="16.5" cy="14" r=".5" /></svg>
);
