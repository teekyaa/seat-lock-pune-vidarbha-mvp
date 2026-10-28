import Link from "next/link";
import { RouteMark } from "@/components/RouteMark";

export default function NotFound() {
  return (
    <div className="flex min-h-[70dvh] flex-col items-center justify-center gap-4 text-center">
      <RouteMark origin="Here" destination="Nowhere" size="lg" />
      <h1 className="text-2xl font-extrabold">This page took a wrong turn</h1>
      <p className="text-base text-muted">The ride or booking may have been removed, or the link is incomplete.</p>
      <Link href="/" className="btn-primary">Find a ride</Link>
    </div>
  );
}
