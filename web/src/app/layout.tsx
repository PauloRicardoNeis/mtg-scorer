import type { Metadata } from "next";
import Link from "next/link";
import { SectionTag, SiteNav } from "@/components/site-nav";
import { HeaderSearch } from "@/components/header-search";
import { LanguageSelect } from "@/components/language-select";
import { I18nProvider } from "@/i18n/context";
import { getI18n } from "@/i18n/server";
import "./tokens.css";
import "./styles.css";

export async function generateMetadata(): Promise<Metadata> {
  const { t } = await getI18n();
  return { title: t.meta.title, description: t.meta.description };
}

export default async function Layout({
  children,
}: {
  children: React.ReactNode;
}) {
  const { locale, t, rich } = await getI18n();
  return (
    <html lang={locale}>
      <body>
        <I18nProvider locale={locale} messages={t}>
          <a className="skip-link" href="#main">
            {t.layout.skip}
          </a>
          <header className="site-header">
            <div className="site-header-inner">
              <div className="brand-group">
                <Link className="brand" href="/cards">
                  MTG Scorer
                </Link>
                <SectionTag />
              </div>
              <SiteNav />
              <HeaderSearch />
            </div>
          </header>
          <main id="main" tabIndex={-1}>
            {children}
          </main>
          <footer className="site-footer">
            <div className="site-footer-inner">
              <div>
                <p className="footer-mark">MTG Scorer</p>
                <p>{t.layout.tagline}</p>
                <LanguageSelect />
              </div>
              <div>
                <p>
                  {rich(t.layout.sources, {
                    topdeck: (
                      <a href="https://topdeck.gg" rel="noreferrer">
                        TopDeck.gg
                      </a>
                    ),
                  })}
                </p>
                {/* The Fan Content Policy notice keeps Wizards' own wording. */}
                <p lang="en">
                  Magic: The Gathering is a trademark of Wizards of the Coast.
                  MTG Scorer is unofficial Fan Content permitted under the Fan
                  Content Policy. Not approved/endorsed by Wizards. Portions of
                  the materials used are property of Wizards of the Coast.
                  ©Wizards of the Coast LLC.
                </p>
              </div>
            </div>
          </footer>
        </I18nProvider>
      </body>
    </html>
  );
}
