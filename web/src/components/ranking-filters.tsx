"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useRef, useTransition } from "react";
import { count } from "@/lib/format";
import { ColorFilter } from "./mana";
import { rememberFocus, useRefocus } from "./refocus";

const cardTypes = [
  ["creature", "Creatures"],
  ["planeswalker", "Planeswalkers"],
  ["instant", "Instants"],
  ["sorcery", "Sorceries"],
  ["artifact", "Artifacts"],
  ["enchantment", "Enchantments"],
  ["land", "Lands"],
];

export type WindowOption = { scoreRunId: string; label: string };

export type SourceTab = {
  source: string;
  label: string;
  href: string;
  current: boolean;
};

export type GradingOption = {
  /** Empty for the run's default method, which the address leaves out. */
  value: string;
  label: string;
  /** A method that could not score this run, e.g. without archetype labels. */
  disabled: boolean;
};

export type ViewTab = {
  view: string;
  label: string;
  count: number;
  href: string;
  current: boolean;
};

/** The form's set values as a query; the API rejects empty ones. */
function values(form: HTMLFormElement): URLSearchParams {
  const query = new URLSearchParams();
  for (const [key, value] of new FormData(form))
    if (typeof value === "string" && value !== "") query.append(key, value);
  return query;
}

/**
 * The views, grading, colors and card type of one pinned run. Each change replaces
 * the URL, so the server re-ranks; without JavaScript the form submits as a GET.
 * Sorting lives in the table's column headers and the name search in the header.
 */
export function RankingFilters({
  format,
  scoreRunId,
  query,
  clearHref,
  views,
  windows = [],
  sources = [],
  gradings = [],
  method = "",
}: {
  format: string;
  scoreRunId: string;
  query: string;
  clearHref: string;
  views: ViewTab[];
  windows?: WindowOption[];
  sources?: SourceTab[];
  gradings?: GradingOption[];
  method?: string;
}) {
  const router = useRouter();
  const [pending, startTransition] = useTransition();
  const form = useRef<HTMLFormElement>(null);
  const current = new URLSearchParams(query);
  const colors = current.getAll("color");
  const type = current.get("type") ?? "";
  // Kept as they are: a filter change re-ranks under the same order, view and size.
  const kept = ["q", "sort", "order", "view", "limit"].flatMap((key) => {
    const value = current.get(key);
    return value ? [[key, value] as const] : [];
  });
  const filtered = Boolean(current.get("q") || type || colors.length);
  // A link elsewhere (clear filters, the header search, history) changes the
  // address without remounting the form, so its controls follow the address.
  const colorKey = colors.join();
  useEffect(() => {
    const controls = form.current!.elements;
    for (const box of controls.namedItem("color") as RadioNodeList)
      (box as HTMLInputElement).checked = colorKey
        .split(",")
        .includes((box as HTMLInputElement).value);
    (controls.namedItem("type") as HTMLSelectElement).value = type;
    (
      controls.namedItem("score_run_id") as HTMLInputElement | HTMLSelectElement
    ).value = scoreRunId;
    const grading = controls.namedItem("method");
    if (grading instanceof HTMLSelectElement) grading.value = method;
  }, [colorKey, type, scoreRunId, method]);
  useRefocus(form, `${scoreRunId}?${query}`);
  const apply = () =>
    startTransition(() =>
      router.replace(`/rankings?${values(form.current!)}`, { scroll: false }),
    );
  return (
    <form
      ref={form}
      className="toolbar band ranking-toolbar"
      action="/rankings"
      method="get"
      aria-label="Ranking filters"
      aria-busy={pending || undefined}
      onChange={(event) => {
        rememberFocus(event.target);
        apply();
      }}
      onSubmit={(event) => {
        event.preventDefault();
        apply();
      }}
    >
      <div className="toolbar-inner band-inner">
        <input type="hidden" name="format" value={format} />
        {windows.length < 2 && (
          <input type="hidden" name="score_run_id" value={scoreRunId} />
        )}
        {gradings.length < 2 && method && (
          <input type="hidden" name="method" value={method} />
        )}
        {kept.map(([key, value]) => (
          <input key={key} type="hidden" name={key} value={value} />
        ))}
        <nav className="view-tabs" aria-label="Views">
          {views.map((tab) => (
            <Link
              key={tab.view}
              href={tab.href}
              aria-current={tab.current ? "page" : undefined}
              scroll={false}
            >
              {tab.label}
              <span className="tab-count">{count(tab.count)}</span>
            </Link>
          ))}
        </nav>
        <span role="status" className="toolbar-status">
          {pending ? "Updating rankings…" : ""}
        </span>
        {gradings.length > 1 && (
          <span className="select">
            <select aria-label="Grading" name="method" defaultValue={method}>
              {gradings.map((grading) => (
                <option
                  key={grading.value}
                  value={grading.value}
                  disabled={grading.disabled}
                >
                  {grading.label}
                </option>
              ))}
            </select>
          </span>
        )}
        <ColorFilter label="Colors" name="color" selected={colors} hideLabel />
        <span className="select">
          <select aria-label="Card type" name="type" defaultValue={type}>
            <option value="">All card types</option>
            {cardTypes.map(([value, label]) => (
              <option key={value} value={value}>
                {label}
              </option>
            ))}
          </select>
        </span>
        {windows.length > 1 && (
          <span className="select">
            <select
              aria-label="Window"
              name="score_run_id"
              defaultValue={scoreRunId}
            >
              {windows.map((window) => (
                <option key={window.scoreRunId} value={window.scoreRunId}>
                  {window.label}
                </option>
              ))}
            </select>
          </span>
        )}
        {sources.length > 1 && (
          <nav className="segmented sm source-tabs" aria-label="Sources">
            {sources.map((tab) => (
              <Link
                key={tab.source}
                href={tab.href}
                aria-current={tab.current ? "page" : undefined}
              >
                {tab.label}
              </Link>
            ))}
          </nav>
        )}
        {filtered && (
          <Link className="button ghost sm" href={clearHref}>
            Clear filters
          </Link>
        )}
        <noscript>
          <button type="submit" className="sm">
            Apply
          </button>
        </noscript>
      </div>
    </form>
  );
}
