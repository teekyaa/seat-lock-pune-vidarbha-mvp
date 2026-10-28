import type { MetadataRoute } from "next";

export default function manifest(): MetadataRoute.Manifest {
  return {
    name: "Seat Lock",
    short_name: "Seat Lock",
    description: "Cost-sharing carpools between Pune and Vidarbha.",
    start_url: "/",
    display: "standalone",
    background_color: "#f5f6f4",
    theme_color: "#1f7a5e",
    icons: [
      { src: "/icon.svg", sizes: "any", type: "image/svg+xml", purpose: "any" },
    ],
  };
}
