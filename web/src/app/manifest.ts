import type { MetadataRoute } from "next";

export default function manifest(): MetadataRoute.Manifest {
  return {
    name: "Seat Lock",
    short_name: "Seat Lock",
    description: "Cost-sharing carpools between Pune and Vidarbha.",
    start_url: "/",
    scope: "/",
    display: "standalone",
    orientation: "portrait",
    background_color: "#f2f4f1",
    theme_color: "#f2f4f1",
    icons: [
      { src: "/pwa-icon/192", sizes: "192x192", type: "image/png", purpose: "any" },
      { src: "/pwa-icon/512", sizes: "512x512", type: "image/png", purpose: "any" },
      { src: "/pwa-icon/512-maskable", sizes: "512x512", type: "image/png", purpose: "maskable" },
    ],
    shortcuts: [
      { name: "Find a seat", url: "/" },
      { name: "Your trips", url: "/bookings" },
      { name: "Offer a ride", url: "/rides/new" },
    ],
  };
}
