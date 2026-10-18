import type { Printing } from "./api";

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

const colorNames: Record<string, string> = {
  W: "White",
  U: "Blue",
  B: "Black",
  R: "Red",
  G: "Green",
};
export function colors(values: string[] | null): string {
  return values === null
    ? "Unknown color identity"
    : values.length === 0
      ? "Colorless"
      : values.map((value) => colorNames[value] ?? value).join(" · ");
}

/** "Magic 2011 #149 (EN)": names a printing in image alt text. */
export function edition(printing: Printing): string {
  return `${printing.set_name} #${printing.collector_number} (${printing.language.toUpperCase()})`;
}
