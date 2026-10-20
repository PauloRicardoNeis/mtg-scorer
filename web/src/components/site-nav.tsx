"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useI18n } from "#i18n";
import type { Messages } from "@/i18n/types";

const links: { href: string; label: keyof Messages["nav"] }[] = [
  { href: "/rankings", label: "rankings" },
  { href: "/cards", label: "discovery" },
  { href: "/datasets", label: "methodology" },
];

/** The current section's name after the wordmark, e.g. "DISCOVERY". */
export function SectionTag() {
  const pathname = usePathname();
  const { t } = useI18n();
  const section = links.find(({ href }) => pathname.startsWith(href));
  if (!section) return null;
  return (
    <>
      <span aria-hidden="true" className="brand-divider" />
      <span className="section-tag">{t.nav[section.label]}</span>
    </>
  );
}

export function SiteNav() {
  const pathname = usePathname();
  const { t } = useI18n();
  return (
    <nav aria-label={t.nav.main} className="site-nav">
      {links.map(({ href, label }) => (
        <Link
          key={href}
          href={href}
          aria-current={pathname.startsWith(href) ? "page" : undefined}
        >
          {t.nav[label]}
        </Link>
      ))}
    </nav>
  );
}
