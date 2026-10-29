import Link from "next/link";
import { redirect } from "next/navigation";
import { PageHeader } from "@/components/PageHeader";
import { api, getMe } from "@/lib/server";
import type { InboxItem } from "@/lib/types";
import { MarkRead } from "./MarkRead";

export const metadata = { title: "Inbox" };

export default async function InboxPage() {
  const me = await getMe();
  if (!me) redirect("/login?next=/inbox");
  const inbox = await api<{ unread: number; items: InboxItem[] }>("/me/notifications");
  return (
    <div className="pad-tabbar">
      <PageHeader title="Inbox" subtitle="Trip updates and reminders" />
      {inbox.items.length === 0 ? (
        <p className="card text-base text-muted">Nothing yet. Requests, payments and reminders for your trips show up here.</p>
      ) : (
        <ul className="card divide-y divide-line p-0">
          {inbox.items.map((n) => (
            <li key={n.id}>
              <Link href={n.url || "/"} className="flex gap-3 px-4 py-3.5 active:bg-paper">
                <span className={`mt-2 h-2.5 w-2.5 shrink-0 rounded-full ${n.read ? "bg-transparent" : "bg-brand"}`} aria-label={n.read ? undefined : "Unread"} />
                <span className="min-w-0">
                  <span className="block font-bold">{n.title}</span>
                  <span className="block text-sm leading-relaxed">{n.body}</span>
                  <span className="mt-1 block text-xs text-muted">{n.sent_at.ist}</span>
                </span>
              </Link>
            </li>
          ))}
        </ul>
      )}
      {inbox.unread > 0 && <MarkRead />}
    </div>
  );
}
