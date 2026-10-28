import Link from "next/link";
import { redirect } from "next/navigation";
import { api, getMe } from "@/lib/server";
import type { InboxItem } from "@/lib/types";
import { MarkRead } from "./MarkRead";

export const metadata = { title: "Inbox" };

export default async function InboxPage() {
  const me = await getMe();
  if (!me) redirect("/login?next=/inbox");
  const inbox = await api<{ unread: number; items: InboxItem[] }>("/me/notifications");
  return (
    <div className="space-y-3">
      <h1 className="text-2xl font-bold">Inbox</h1>
      {inbox.items.length === 0 && <p className="card text-sm text-muted">Trip updates and reminders show up here.</p>}
      {inbox.items.map((n) => (
        <Link key={n.id} href={n.url || "/"} className={`card block ${n.read ? "" : "border-brand/40"}`}>
          <p className="font-semibold">{!n.read && <span className="mr-1 inline-block h-2 w-2 rounded-full bg-brand" />}{n.title}</p>
          <p className="text-sm">{n.body}</p>
          <p className="mt-1 text-xs text-muted">{n.sent_at.ist}</p>
        </Link>
      ))}
      {inbox.unread > 0 && <MarkRead />}
    </div>
  );
}
