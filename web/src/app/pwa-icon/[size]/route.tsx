import { appIcon } from "@/lib/appIcon";

// /pwa-icon/192, /pwa-icon/512 and /pwa-icon/512-maskable for the web app manifest.
export async function GET(_: Request, { params }: { params: Promise<{ size: string }> }) {
  const { size } = await params;
  const maskable = size.endsWith("-maskable");
  const px = Number.parseInt(size, 10);
  if (![192, 512].includes(px)) return new Response("Not found", { status: 404 });
  return appIcon(px, maskable ? 0.22 : 0.1);
}
