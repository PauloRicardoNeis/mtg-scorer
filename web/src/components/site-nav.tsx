"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

const links = [
  { href: "/rankings", label: "Rankings" },
  { href: "/cards", label: "Discovery" },
  { href: "/datasets", label: "Methodology" },
];

/** The current section's name after the wordmark, e.g. "DISCOVERY". */
export function SectionTag() {
  const pathname = usePathname();
  const section = links.find(({ href }) => pathname.startsWith(href));
  if (!section) return null;
  return (
    <>
      <span aria-hidden="true" className="brand-divider" />
      <span className="section-tag">{section.label}</span>
    </>
  );
}

export function SiteNav() {
  const pathname = usePathname();
  return (
    <nav aria-label="Main" className="site-nav">
      {links.map(({ href, label }) => (
        <Link
          key={href}
          href={href}
          aria-current={pathname.startsWith(href) ? "page" : undefined}
        >
          {label}
        </Link>
      ))}
    </nav>
  );
}
