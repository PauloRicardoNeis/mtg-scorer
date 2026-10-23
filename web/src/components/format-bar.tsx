"use client";

import Link from "next/link";
import { useEffect, useRef } from "react";
import { useI18n } from "#i18n";
import type { I18n } from "@/i18n/translator";
import { Icon } from "./icon";

export type FormatTab = {
  label: string;
  format: string;
  decks: number | null;
  /** The overall run, which spans every format and has its own grading. */
  overall?: boolean;
};

/** "2,448 decks" → "2.4k decks" once a count passes a thousand. */
function decks(value: number, { t, fill, plural, decimal }: I18n): string {
  if (value < 1000) return plural(t.formats.decks, value);
  return fill(t.formats.thousandDecks, {
    count: decimal(value / 1000, value < 10_000 ? 1 : 0),
  });
}

/**
 * The formats as two-line tabs: a dot and the name, then the deck count. A format
 * without published rankings stays visible but cannot be opened. The bar scrolls
 * sideways, and the current format scrolls into view. The overall tab leads and
 * keeps its own grading; the last tab compares formats, unless the page ranks
 * something cards cannot be compared by, such as commanders.
 */
export function FormatBar({
  tabs,
  current,
  comparing = false,
  query = "",
  compareQuery = "",
  path = "/rankings",
  compare = true,
}: {
  tabs: FormatTab[];
  current: string | null;
  comparing?: boolean;
  /** Choices that follow the reader to another format, such as the grading. */
  query?: string;
  /** Choices that follow the reader to the comparison, which grades by fewer methods. */
  compareQuery?: string;
  /** The page each format's tab opens. */
  path?: string;
  compare?: boolean;
}) {
  const i18n = useI18n();
  const { t } = i18n;
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
        aria-label={t.formats.label}
      >
        {tabs.map((tab) => {
          const active = tab.format === current;
          const ready = tab.decks !== null;
          // Another format's grading does not apply to the overall run.
          const kept = tab.overall ? "" : query;
          return (
            <Link
              key={tab.format}
              className={
                tab.overall ? "format-tab format-tab-overall" : "format-tab"
              }
              href={`${path}?format=${encodeURIComponent(tab.format)}${kept && `&${kept}`}`}
              aria-current={active ? "page" : undefined}
              aria-disabled={ready ? undefined : true}
              tabIndex={ready ? undefined : -1}
            >
              <span className="format-tab-label">
                {tab.overall ? (
                  <Icon name="layers" size={12} />
                ) : (
                  <span className="format-dot" aria-hidden="true" />
                )}
                {tab.label}
              </span>
              <span className="format-tab-sub">
                {ready ? decks(tab.decks!, i18n) : t.formats.noData}
              </span>
            </Link>
          );
        })}
        {compare && (
          <Link
            className="format-tab format-tab-all"
            href={`/rankings/compare${compareQuery && `?${compareQuery}`}`}
            aria-current={comparing ? "page" : undefined}
          >
            <span className="format-tab-label">
              <Icon name="layout-grid" size={12} />
              {t.formats.allFormats}
            </span>
            <span className="format-tab-sub">{t.formats.compare}</span>
          </Link>
        )}
      </nav>
    </div>
  );
}
