import { createElement, Fragment, type ReactNode } from "react";
import * as format from "@/lib/format";
import type { Locale } from "./locales";
import type { MethodText, Messages, Plural } from "./types";

export type Values = Record<string, string | number>;

/**
 * One language's messages with the formatters that go with them: numbers, dates and
 * plurals the locale's way. Pages and components take it from useI18n().
 */
export type I18n = {
  locale: Locale;
  t: Messages;
  /** A message with its {placeholders} filled; numbers get the locale's digits. */
  fill: (template: string, values: Values) => string;
  /** The plural form for `count`, with {count} and any other values filled. */
  plural: (forms: Plural, count: number, values?: Values) => string;
  /** A message whose placeholders are elements, such as a link inside a sentence. */
  rich: (template: string, parts: Record<string, ReactNode>) => ReactNode;
  /** A capitalized name as it reads mid-sentence: lowercase, except where nouns keep capitals. */
  term: (name: string) => string;
  /** A score method's name and description in this language, else the run's own. */
  method: (method: { method_id: string } & MethodText) => MethodText;
  /** Color identity in words: "White · Blue", "Colorless". */
  colors: (values: string[] | null) => string;
  count: (value: number) => string;
  decimal: (value: number, digits: 0 | 1 | 2) => string;
  signed: (value: number) => string;
  percent: (points: number) => string;
  lift: (ratio: number) => string;
  share: (part: number, whole: number) => string;
  usd: (value: number) => string;
  /** A deck or card price: "$4.20", or whole dollars from $100: "$1,284". */
  price: (value: number) => string;
  /** A count, in thousands past a thousand: "940", "1.2k". */
  compact: (value: number) => string;
  perDollar: (value: number) => string;
  dateWindow: (startsOn: string, endsBefore: string) => string;
  dateWithYear: (instant: string) => string;
  /** An ISO date without its year: "Oct 13". */
  day: (isoDate: string) => string;
  dateTime: (instant: string) => string;
  /** A published window as the window select names it: "Last 90 days", "Since Jan 1, 2024". */
  windowLabel: (
    startsOn: string,
    endsBefore: string,
    latestEnd: string,
  ) => string;
  /** How long ago an instant was: "2 hours ago", "yesterday", "just now". */
  ago: (instant: string, now?: Date) => string;
};

const placeholder = /\{(\w+)\}/g;

// German capitalizes nouns, so a method's name keeps its capitals mid-sentence.
const capitalizedNouns = new Set<Locale>(["de"]);

export function createI18n(locale: Locale, t: Messages): I18n {
  const rules = new Intl.PluralRules(locale);
  const count = (value: number) => format.count(value, locale);
  const fill = (template: string, values: Values) =>
    template.replace(placeholder, (hole, name: string) => {
      const value = values[name];
      if (value === undefined) return hole;
      return typeof value === "number" ? count(value) : value;
    });
  const plural = (forms: Plural, n: number, values: Values = {}) =>
    fill(forms[rules.select(n)] ?? forms.other, { ...values, count: n });
  const dateWindow = (startsOn: string, endsBefore: string) =>
    format.dateWindow(startsOn, endsBefore, locale);
  const dateWithYear = (instant: string) =>
    format.dateWithYear(instant, locale);
  return {
    locale,
    t,
    fill,
    plural,
    rich: (template, parts) =>
      template
        .split(/\{(\w+)\}/)
        .map((piece, index) =>
          index % 2 === 0
            ? piece
            : createElement(
                Fragment,
                { key: index },
                parts[piece] ?? `{${piece}}`,
              ),
        ),
    term: (name) =>
      capitalizedNouns.has(locale) ? name : name.toLocaleLowerCase(locale),
    method: ({ method_id, label, description }) =>
      t.methods[method_id] ?? { label, description },
    colors: (values) =>
      values === null
        ? t.colors.unknown
        : values.length === 0
          ? t.colors.C
          : values
              .map(
                (value) => t.colors[value as keyof Messages["colors"]] ?? value,
              )
              .join(" · "),
    count,
    decimal: (value, digits) => format.decimal(value, digits, locale),
    signed: (value) => format.signed(value, locale),
    percent: (points) => format.percent(points, locale),
    lift: (ratio) => format.lift(ratio, locale),
    share: (part, whole) => format.share(part, whole, locale),
    usd: (value) => format.usd(value, locale),
    price: (value) => format.price(value, locale),
    compact: (value) =>
      value < 1000
        ? count(value)
        : fill(t.metagame.thousands, {
            count: format.decimal(value / 1000, 1, locale),
          }),
    perDollar: (value) => format.perDollar(value, locale),
    dateWindow,
    dateWithYear,
    day: (isoDate) => format.day(isoDate, locale),
    dateTime: (instant) => format.dateTime(instant, locale),
    windowLabel: (startsOn, endsBefore, latestEnd) => {
      if (endsBefore !== latestEnd) return dateWindow(startsOn, endsBefore);
      const days = format.daysBetween(startsOn, endsBefore);
      return days <= 120
        ? plural(t.time.lastDays, days)
        : fill(t.time.since, { date: dateWithYear(`${startsOn}T00:00:00Z`) });
    },
    ago: (instant, now) => format.ago(instant, now, locale) ?? t.time.justNow,
  };
}
