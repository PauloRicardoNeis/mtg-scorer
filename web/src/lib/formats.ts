// The design's formats always show, so missing data is visible; any other format
// with a published run follows them. TopDeck's EDH events are competitive
// Commander, so that run fills the Commander tab.
export const designFormats: [label: string, format: string][] = [
  ["Standard", "Standard"],
  ["Pioneer", "Pioneer"],
  ["Modern", "Modern"],
  ["Legacy", "Legacy"],
  ["Vintage", "Vintage"],
  ["Pauper", "Pauper"],
  ["Commander", "EDH"],
];

/**
 * The overall run: every format's grade combined into one per card. It leads the
 * format bar and is never compared, since it already spans the formats.
 */
export const OVERALL_FORMAT = "Overall";

/** A format as the site names it: TopDeck's "EDH" reads "Commander". */
export function formatLabel(format: string): string {
  return designFormats.find(([, name]) => name === format)?.[0] ?? format;
}
