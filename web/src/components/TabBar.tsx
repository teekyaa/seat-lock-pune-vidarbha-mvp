"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { BellIcon, PlusIcon, SearchIcon, TicketIcon, UserIcon } from "./icons";

const TABS = [
  { href: "/", label: "Find", Icon: SearchIcon, match: (p: string) => p === "/" },
  { href: "/bookings", label: "Trips", Icon: TicketIcon, match: (p: string) => p === "/bookings" },
  { href: "/rides/new", label: "Offer", Icon: PlusIcon, match: (p: string) => p === "/rides/new", primary: true },
  { href: "/inbox", label: "Inbox", Icon: BellIcon, match: (p: string) => p === "/inbox" },
  { href: "/me", label: "Me", Icon: UserIcon, match: (p: string) => p === "/me" || p.startsWith("/u/") },
];

// Pushed screens (a ride, a booking, posting, sign-in) hide the tab bar and use a back button
// plus their own sticky action bar, the way native iOS and Android navigation stacks work.
const HIDDEN = [/^\/r\//, /^\/bookings\/.+/, /^\/rides\/new/, /^\/login/];

export function TabBar({ unread }: { unread: number }) {
  const path = usePathname();
  if (HIDDEN.some((re) => re.test(path))) return null;
  return (
    <nav
      aria-label="Main"
      className="fixed inset-x-0 bottom-0 z-30 border-t border-line bg-surface/95 backdrop-blur-md"
      style={{ paddingBottom: "var(--safe-bottom)" }}
    >
      <ul className="mx-auto grid h-[var(--tabbar-h)] max-w-md grid-cols-5">
        {TABS.map(({ href, label, Icon, match, primary }) => {
          const active = match(path);
          return (
            <li key={href}>
              <Link
                href={href}
                aria-current={active ? "page" : undefined}
                className={`flex h-full flex-col items-center justify-center gap-0.5 text-[11px] font-semibold ${
                  active ? "text-brand" : "text-muted"
                }`}
              >
                {primary ? (
                  <span className="grid h-9 w-12 place-items-center rounded-full bg-brand text-white">
                    <Icon className="h-5 w-5" />
                  </span>
                ) : (
                  <span className="relative">
                    <Icon />
                    {label === "Inbox" && unread > 0 && (
                      <span className="absolute -right-2 -top-1 grid h-4 min-w-4 place-items-center rounded-full bg-danger px-1 text-[10px] text-white">
                        {unread > 9 ? "9+" : unread}
                      </span>
                    )}
                  </span>
                )}
                {label}
              </Link>
            </li>
          );
        })}
      </ul>
    </nav>
  );
}
