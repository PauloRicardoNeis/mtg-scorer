import type { Metadata } from "next";

import "./globals.css";

export const metadata: Metadata = {
  title: "MTG Scorer — Forge Discovery",
  description: "Find historically interesting Magic cards and inspect the evidence behind them.",
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
