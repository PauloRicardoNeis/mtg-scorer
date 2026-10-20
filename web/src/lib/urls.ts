import type { Printing, RankedCard } from "./api";

export type SearchParams = Record<string, string | string[] | undefined>;

export function queryParams(values: SearchParams): URLSearchParams {
  const query = new URLSearchParams();
  for (const [key, value] of Object.entries(values)) {
    for (const item of Array.isArray(value)
      ? value
      : value === undefined
        ? []
        : [value])
      query.append(key, item);
  }
  return query;
}

export function printingParams(query: URLSearchParams): URLSearchParams {
  const result = new URLSearchParams();
  for (const key of ["catalog_snapshot_id", "set", "rarity", "game", "limit"]) {
    for (const value of query.getAll(key)) result.append(key, value);
  }
  return result;
}

/** "Magic 2011 #149 (EN)": names a printing in image alt text. */
export function edition(printing: Printing): string {
  return `${printing.set_name} #${printing.collector_number} (${printing.language.toUpperCase()})`;
}

/** A ranked card's catalog page, pinned to the catalog the ranking joined; null when it is not in it. */
export function rankedCardHref(
  card: Pick<RankedCard, "oracle_id" | "preview_printing">,
  catalogSnapshotId: string | null,
): string | null {
  if (!card.preview_printing || !catalogSnapshotId) return null;
  const query = new URLSearchParams({ catalog_snapshot_id: catalogSnapshotId });
  return `/cards/${encodeURIComponent(card.oracle_id)}?${query}`;
}
