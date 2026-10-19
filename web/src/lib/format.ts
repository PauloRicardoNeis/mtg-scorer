// Shared number formatting for statistics. Every helper uses the true minus sign
// (U+2212) so negative values line up with positive ones in mono type.
const MINUS = "−";

function decimal(value: number, digits: number): string {
  return Math.abs(value) < 0.5 * 10 ** -digits
    ? (0).toFixed(digits)
    : value.toFixed(digits).replace("-", MINUS);
}

/** Thousands separators: 33512 → "33,512". */
export function count(value: number): string {
  return value.toLocaleString("en-US").replace("-", MINUS);
}

/** A delta with an explicit sign and one decimal: "+2.4", "−0.8", "0.0". */
export function signed(value: number): string {
  const text = decimal(value, 1);
  return value >= 0.05 ? `+${text}` : text;
}

/** A value already in percentage points, with one decimal: 54.12 → "54.1%". */
export function percent(points: number): string {
  return `${decimal(points, 1)}%`;
}

/** A ratio to the field with two decimals: 1.123 → "1.12×". */
export function lift(ratio: number): string {
  return `${decimal(ratio, 2)}×`;
}

/** Places gained (positive) or lost since the previous period: "▲ 3", "▼ 2", "—". */
export function movement(places: number): string {
  return places > 0 ? `▲ ${places}` : places < 0 ? `▼ ${-places}` : "—";
}

export type Tone = "positive" | "negative" | "neutral";

/** Win-rate deltas count as a signal from ±0.05 percentage points. */
export function deltaTone(points: number): Tone {
  return points >= 0.05 ? "positive" : points <= -0.05 ? "negative" : "neutral";
}

/** Top-cut lift is strong from 1.10× and weak below 0.97×. */
export function liftTone(ratio: number): Tone {
  return ratio >= 1.1 ? "positive" : ratio < 0.97 ? "negative" : "neutral";
}

const bands: [number, string][] = [
  [90, "A+"],
  [85, "A"],
  [80, `A${MINUS}`],
  [75, "B+"],
  [70, "B"],
  [65, `B${MINUS}`],
  [60, "C+"],
  [50, "C"],
  [45, `C${MINUS}`],
  [35, "D"],
];

/** Letter grade for a 0–100 score. */
export function grade(score: number): string {
  return bands.find(([floor]) => score >= floor)?.[1] ?? "F";
}

export type GradeTone = "a" | "b" | "c" | "d" | "f";

/** Tone class for a grade: A is accent, B text-1, C text-3, D warning, F danger. */
export function gradeTone(letter: string): GradeTone {
  return letter[0].toLowerCase() as GradeTone;
}

/** A part of a known whole as a percentage with one decimal: 37 of 231 → "16.0%". */
export function share(part: number, whole: number): string {
  return whole > 0 ? percent((100 * part) / whole) : "—";
}

const day = new Intl.DateTimeFormat("en-US", {
  month: "short",
  day: "numeric",
  timeZone: "UTC",
});
const dayWithYear = new Intl.DateTimeFormat("en-US", {
  month: "short",
  day: "numeric",
  year: "numeric",
  timeZone: "UTC",
});

/** An ISO window with an exclusive end, as inclusive days: "Mar 1 – Aug 31, 2026". */
export function dateWindow(startsOn: string, endsBefore: string): string {
  const start = new Date(`${startsOn}T00:00:00Z`);
  const end = new Date(Date.parse(`${endsBefore}T00:00:00Z`) - 86_400_000);
  const first =
    start.getUTCFullYear() === end.getUTCFullYear()
      ? day.format(start)
      : dayWithYear.format(start);
  return `${first} – ${dayWithYear.format(end)}`;
}
