"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useRef, useTransition } from "react";
import { ColorFilter } from "./mana";

const cardTypes = [
  ["creature", "Creatures"],
  ["planeswalker", "Planeswalkers"],
  ["instant", "Instants"],
  ["sorcery", "Sorceries"],
  ["artifact", "Artifacts"],
  ["enchantment", "Enchantments"],
  ["land", "Lands"],
];

const sorts = [
  ["score", "Sort: Relative volume"],
  ["decks", "Sort: Meta share"],
  ["top_cuts", "Sort: Top cuts"],
  ["name", "Sort: Name A–Z"],
];

/** The form's set values as a query; the API rejects empty ones. */
function values(form: HTMLFormElement): URLSearchParams {
  const query = new URLSearchParams();
  for (const [key, value] of new FormData(form))
    if (typeof value === "string" && value !== "") query.append(key, value);
  return query;
}

/**
 * Color, type and sort for one pinned run. Each change replaces the URL, so the
 * server re-ranks; without JavaScript the form submits as a plain GET.
 */
export function RankingFilters({
  format,
  scoreRunId,
  query,
  clearHref,
}: {
  format: string;
  scoreRunId: string;
  query: string;
  clearHref: string;
}) {
  const router = useRouter();
  const [pending, startTransition] = useTransition();
  const form = useRef<HTMLFormElement>(null);
  const current = new URLSearchParams(query);
  const colors = current.getAll("color");
  const type = current.get("type") ?? "";
  const sort = current.get("sort") ?? "score";
  const q = current.get("q");
  const limit = current.get("limit");
  const filtered = Boolean(q || type || colors.length);
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
    (controls.namedItem("sort") as HTMLSelectElement).value = sort;
  }, [colorKey, type, sort]);
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
      onChange={apply}
      onSubmit={(event) => {
        event.preventDefault();
        apply();
      }}
    >
      <div className="toolbar-inner band-inner">
        <input type="hidden" name="format" value={format} />
        <input type="hidden" name="score_run_id" value={scoreRunId} />
        {q && <input type="hidden" name="q" value={q} />}
        {limit && <input type="hidden" name="limit" value={limit} />}
        <span role="status" className="toolbar-status">
          {pending ? "Updating rankings…" : ""}
        </span>
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
        <span className="select">
          <select aria-label="Sort by" name="sort" defaultValue={sort}>
            {sorts.map(([value, label]) => (
              <option key={value} value={value}>
                {label}
              </option>
            ))}
          </select>
        </span>
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
