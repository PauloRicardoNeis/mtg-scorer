"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

const links = [
  { href: "/cards", label: "Discovery" },
  { href: "/datasets", label: "Dataset & method" },
];

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
