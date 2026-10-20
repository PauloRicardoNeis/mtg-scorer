// Shared number formatting for statistics, in the reader's locale ("54.1%", "54,1 %").
// Every helper uses the true minus sign (U+2212) so negative values line up with
// positive ones in mono type.
const MINUS = "−";

/** Builds each locale's formatter once: tables format thousands of values. */
function perLocale<T>(build: (locale: string) => T): (locale: string) => T {
  const built = new Map<string, T>();
  return (locale) => {
    let formatter = built.get(locale);
    if (formatter === undefined) {
      formatter = build(locale);
      built.set(locale, formatter);
    }
    return formatter;
  };
}

const fixed = [0, 1, 2].map((digits) =>
  perLocale(
    (locale) =>
      new Intl.NumberFormat(locale, {
        minimumFractionDigits: digits,
        maximumFractionDigits: digits,
        useGrouping: false,
      }),
  ),
);

/** A value with fixed decimals and no grouping: 87.25 → "87.3" ("87,3" in German). */
export function decimal(value: number, digits: number, locale = "en"): string {
  const shown = Math.abs(value) < 0.5 * 10 ** -digits ? 0 : value;
  return fixed[digits](locale).format(shown).replace("-", MINUS);
}

const counts = perLocale((locale) => new Intl.NumberFormat(locale));

/** Thousands separators: 33512 → "33,512" ("33.512" in German). */
export function count(value: number, locale = "en"): string {
  return counts(locale).format(value).replace("-", MINUS);
}

/** A delta with an explicit sign and one decimal: "+2.4", "−0.8", "0.0". */
export function signed(value: number, locale = "en"): string {
  const text = decimal(value, 1, locale);
  return value >= 0.05 ? `+${text}` : text;
}

// The locale's percent sign and spacing around a number: "%" after it in English,
// " %" after a no-break space in French.
const percentAffixes = perLocale((locale) => {
  const parts = new Intl.NumberFormat(locale, {
    style: "percent",
  }).formatToParts(0.5);
  const at = parts.findIndex((part) => part.type === "integer");
  return [parts.slice(0, at), parts.slice(at + 1)].map((side) =>
    side.map((part) => part.value).join(""),
  );
});

/** A value already in percentage points, with one decimal: 54.12 → "54.1%". */
export function percent(points: number, locale = "en"): string {
  const [before, after] = percentAffixes(locale);
  return `${before}${decimal(points, 1, locale)}${after}`;
}

/** A ratio to the field with two decimals: 1.123 → "1.12×". */
export function lift(ratio: number, locale = "en"): string {
  return `${decimal(ratio, 2, locale)}×`;
}

const dollars = perLocale(
  (locale) =>
    new Intl.NumberFormat(locale, { style: "currency", currency: "USD" }),
);

/** A USD price in cents: 1125.9 → "$1,125.90". */
export function usd(value: number, locale = "en"): string {
  return dollars(locale).format(value);
}

const wholes = perLocale(
  (locale) => new Intl.NumberFormat(locale, { maximumFractionDigits: 0 }),
);
const significant = perLocale(
  (locale) => new Intl.NumberFormat(locale, { maximumSignificantDigits: 3 }),
);

/** Score per dollar: whole from 100 ("1,667"), else three figures ("41.2", "0.0621"). */
export function perDollar(value: number, locale = "en"): string {
  return (value >= 100 ? wholes : significant)(locale).format(value);
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
export function share(part: number, whole: number, locale = "en"): string {
  return whole > 0 ? percent((100 * part) / whole, locale) : "—";
}

const days = perLocale(
  (locale) =>
    new Intl.DateTimeFormat(locale, {
      month: "short",
      day: "numeric",
      year: "numeric",
      timeZone: "UTC",
    }),
);

/**
 * An ISO window with an exclusive end, as inclusive days the locale's way: "Mar 1 –
 * Aug 31, 2026", "1. März – 31. Aug. 2026". A shared year or month shows once.
 */
export function dateWindow(
  startsOn: string,
  endsBefore: string,
  locale = "en",
): string {
  const start = new Date(`${startsOn}T00:00:00Z`);
  const end = new Date(Date.parse(`${endsBefore}T00:00:00Z`) - 86_400_000);
  return days(locale).formatRange(start, end);
}

/** An instant's UTC day with its year: "Sep 27, 2026". */
export function dateWithYear(instant: string, locale = "en"): string {
  return days(locale).format(new Date(instant));
}

const instants = perLocale(
  (locale) =>
    new Intl.DateTimeFormat(locale, {
      dateStyle: "long",
      timeStyle: "short",
      timeZone: "UTC",
    }),
);

/** An instant to the minute, in UTC: "October 19, 2026 at 12:00 PM". */
export function dateTime(instant: string, locale = "en"): string {
  return `${instants(locale).format(new Date(instant))} UTC`;
}

const relativeTime = perLocale(
  (locale) => new Intl.RelativeTimeFormat(locale, { numeric: "auto" }),
);
const units: [Intl.RelativeTimeFormatUnit, number][] = [
  ["year", 365 * 86_400],
  ["month", 30 * 86_400],
  ["week", 7 * 86_400],
  ["day", 86_400],
  ["hour", 3_600],
  ["minute", 60],
];

/**
 * How long ago an instant was, in its largest whole unit: "2 hours ago", "yesterday";
 * null under a minute, which callers word themselves.
 */
export function ago(
  instant: string,
  now: Date = new Date(),
  locale = "en",
): string | null {
  // A clock slightly behind the publisher's still reads as just now.
  const seconds = Math.max(0, (now.getTime() - Date.parse(instant)) / 1000);
  for (const [unit, size] of units)
    if (seconds >= size)
      return relativeTime(locale).format(-Math.floor(seconds / size), unit);
  return null;
}

/** Whole days from one ISO date to another: a published window's length. */
export function daysBetween(startsOn: string, endsBefore: string): number {
  return Math.round(
    (Date.parse(`${endsBefore}T00:00:00Z`) -
      Date.parse(`${startsOn}T00:00:00Z`)) /
      86_400_000,
  );
}
