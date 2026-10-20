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

/** A format as the site names it: TopDeck's "EDH" reads "Commander". */
export function formatLabel(format: string): string {
  return designFormats.find(([, name]) => name === format)?.[0] ?? format;
}

// What kind of format each is, under its name. Formats without an entry say
// where their events come from instead.
export const descriptors: Record<string, string> = {
  Standard: "Rotating · 60 cards · 1v1",
  Pioneer: "Non-rotating · Return to Ravnica forward · 1v1",
  Modern: "Non-rotating · Eighth Edition forward · 1v1",
  Legacy: "Eternal · 60 cards · 1v1",
  Vintage: "Eternal · restricted list · 1v1",
  Pauper: "Commons only · 60 cards · 1v1",
  EDH: "cEDH · 100-card singleton · 4-player pods",
};
