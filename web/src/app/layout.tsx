import type { Metadata } from "next";
import Link from "next/link";
import "./styles.css";

export const metadata: Metadata = {
  title: "MTG Scorer · Card discovery",
  description:
    "Explore a real, bounded Magic card catalog and its source dataset. Guest access; no tournament scores.",
};
export default function Layout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body>
        <a className="skip-link" href="#main">
          Skip to content
        </a>
        <header className="site-header">
          <Link className="brand" href="/cards">
            <span aria-hidden="true" className="brand-mark">
              M
            </span>
            MTG Scorer
          </Link>
          <nav aria-label="Main">
            <Link href="/cards">Discovery</Link>
            <Link href="/datasets">Dataset &amp; method</Link>
          </nav>
          <span className="guest">Guest catalog</span>
        </header>
        <main id="main" tabIndex={-1}>
          {children}
        </main>
        <footer>
          Card metadata: Scryfall. Magic: The Gathering is a trademark of
          Wizards of the Coast.
          <br />A bounded catalog sample. Tournament evidence is not available.
        </footer>
      </body>
    </html>
  );
}
