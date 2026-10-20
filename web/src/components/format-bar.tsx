"use client";

import Link from "next/link";
import { useEffect, useRef } from "react";
import { count } from "@/lib/format";
import { Icon } from "./icon";

export type FormatTab = {
  label: string;
  format: string;
  decks: number | null;
};

/** "2,448 decks" → "2.4k decks" once a count passes a thousand. */
function decks(value: number): string {
  if (value < 1000) return `${count(value)} decks`;
  return `${(value / 1000).toFixed(value < 10_000 ? 1 : 0)}k decks`;
}

/**
 * The formats as two-line tabs: a dot and the name, then the deck count. A format
 * without published rankings stays visible but cannot be opened. The bar scrolls
 * sideways, and the current format scrolls into view. The last tab compares formats.
 */
export function FormatBar({
  tabs,
  current,
  comparing = false,
}: {
  tabs: FormatTab[];
  current: string | null;
  comparing?: boolean;
}) {
  const bar = useRef<HTMLElement>(null);
  useEffect(() => {
    const tab = bar.current?.querySelector<HTMLElement>(
      '[aria-current="page"]',
    );
    if (!bar.current || !tab) return;
    const { left, right } = bar.current.getBoundingClientRect();
    const box = tab.getBoundingClientRect();
    // The right edge fades out over 40px, so the tab clears it.
    if (box.right > right - 40)
      bar.current.scrollLeft += box.right - right + 40;
    else if (box.left < left) bar.current.scrollLeft -= left - box.left;
  }, [current, comparing]);
  return (
    <div className="format-bar band">
      <nav
        ref={bar}
        className="format-bar-inner band-inner"
        aria-label="Formats"
      >
        {tabs.map((tab) => {
          const active = tab.format === current;
          const ready = tab.decks !== null;
          return (
            <Link
              key={tab.format}
              className="format-tab"
              href={`/rankings?format=${encodeURIComponent(tab.format)}`}
              aria-current={active ? "page" : undefined}
              aria-disabled={ready ? undefined : true}
              tabIndex={ready ? undefined : -1}
            >
              <span className="format-tab-label">
                <span className="format-dot" aria-hidden="true" />
                {tab.label}
              </span>
              <span className="format-tab-sub">
                {ready ? decks(tab.decks!) : "No data yet"}
              </span>
            </Link>
          );
        })}
        <Link
          className="format-tab format-tab-all"
          href="/rankings/compare"
          aria-current={comparing ? "page" : undefined}
        >
          <span className="format-tab-label">
            <Icon name="layout-grid" size={12} />
            All formats
          </span>
          <span className="format-tab-sub">Compare</span>
        </Link>
      </nav>
    </div>
  );
}
