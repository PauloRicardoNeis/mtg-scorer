import type { Metadata } from "next";
import Link from "next/link";
import { SiteNav } from "@/components/site-nav";
import "./tokens.css";
import "./styles.css";

export const metadata: Metadata = {
  title: "MTG Scorer · Card discovery",
  description:
    "Explore a versioned Magic card catalog and its source dataset. Guest access; no tournament scores.",
};
export default function Layout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body>
        <a className="skip-link" href="#main">
          Skip to content
        </a>
        <header className="site-header">
          <div className="site-header-inner">
            <div className="brand-group">
              <Link className="brand" href="/cards">
                MTG Scorer
              </Link>
              <span aria-hidden="true" className="brand-divider" />
              <span className="guest">Guest catalog</span>
            </div>
            <SiteNav />
          </div>
        </header>
        <main id="main" tabIndex={-1}>
          {children}
        </main>
        <footer className="site-footer">
          <div className="site-footer-inner">
            <div>
              <p className="footer-mark">MTG Scorer</p>
              <p>
                A versioned card catalog. Tournament evidence is not available.
              </p>
            </div>
            <div>
              <p>
                Card metadata and images: Scryfall. Magic: The Gathering is a
                trademark of Wizards of the Coast.
              </p>
              <p>
                MTG Scorer is unofficial Fan Content permitted under the Fan
                Content Policy. Not approved/endorsed by Wizards. Portions of
                the materials used are property of Wizards of the Coast.
                ©Wizards of the Coast LLC.
              </p>
            </div>
          </div>
        </footer>
      </body>
    </html>
  );
}
