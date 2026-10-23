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

/** The card page's query keys for its deck listing: the run shown and the first deck. */
export const DECK_RUN = "decks_run";
export const DECK_OFFSET = "decks_offset";

/** The card page's deck listing as the API's query; an unreadable offset is the first page. */
export function deckParams(query: URLSearchParams): URLSearchParams {
  const result = new URLSearchParams();
  const run = query.get(DECK_RUN);
  if (run) result.set("score_run_id", run);
  const offset = query.get(DECK_OFFSET);
  if (offset && /^[0-9]{1,7}$/.test(offset)) result.set("offset", offset);
  return result;
}

/** The card a deck page was opened from, to mark it and lead back to it. */
export const FROM_CARD = "card";

/**
 * A published deck's page, opened from a card's deck list: it keeps the card, its catalog and
 * the list's run and page, so the deck page can lead back to where the reader was.
 */
export function deckPageHref(
  scoreRun: string,
  position: number,
  card: string,
  query: URLSearchParams,
): string {
  const next = new URLSearchParams({ [FROM_CARD]: card });
  for (const key of ["catalog_snapshot_id", DECK_OFFSET])
    if (query.get(key)) next.set(key, query.get(key)!);
  return `/decks/${encodeURIComponent(scoreRun)}/${position}?${next}`;
}

/** Back from a deck page to the card it was opened from, at the deck list it was in. */
export function cardDecksHref(
  card: string,
  scoreRun: string,
  query: URLSearchParams,
): string {
  const next = new URLSearchParams();
  if (query.get("catalog_snapshot_id"))
    next.set("catalog_snapshot_id", query.get("catalog_snapshot_id")!);
  next.set(DECK_RUN, scoreRun);
  if (query.get(DECK_OFFSET)) next.set(DECK_OFFSET, query.get(DECK_OFFSET)!);
  return `/cards/${encodeURIComponent(card)}?${next}#decks`;
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
