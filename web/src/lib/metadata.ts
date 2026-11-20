import type { Metadata } from "next";

/**
 * The Open Graph tags every page shares. Next replaces the layout's openGraph
 * whole when a page sets its own, so a page that adds a title or an image spreads
 * these in.
 */
export const openGraph = {
  siteName: "MTG Scorer",
  type: "website",
} as const satisfies Metadata["openGraph"];
