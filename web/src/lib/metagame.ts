// View models for the Archetypes and Decklists sections. The Java API has no
// archetype, matchup or decklist endpoints yet, so api.ts serves these shapes from
// the typed sample data in metagame.fixtures.ts; the pages show a "Sample data" tag.

import type { Messages } from "@/i18n/types";
import { designFormats } from "./formats";

export type Color = "W" | "U" | "B" | "R" | "G";

/** A color filter choice: a mana color, or C for colorless decks. */
export type ColorChoice = Color | "C";

export type CardType =
  | "creature"
  | "planeswalker"
  | "instant"
  | "sorcery"
  | "artifact"
  | "enchantment"
  | "battle"
  | "land";

export interface ArchetypeStat {
  /** Slug, e.g. "boros-energy". */
  id: string;
  /** "Boros Energy"; in Commander the commander's name, or "A // B" for partners. */
  name: string;
  /** WUBRG order; [] is colorless. */
  colors: Color[];
  /** Percent of decklists in the window. */
  share: number;
  /** Percent, mirrors excluded (cEDH: pod win rate). */
  win_rate: number;
  /** ± at 95%. */
  win_rate_ci: number;
  /** Top 8 (cEDH Top 16) conversion; 1.00 is the field. */
  top_cut_lift: number;
  /** Matches (cEDH: seats). */
  sample: number;
  deck_count: number;
  /** 14 weekly points, oldest → newest. */
  share_series: number[];
  /** 14 weekly points, oldest → newest. */
  win_rate_series: number[];
  /** Share now − share 30 days ago, in points. */
  trend_30d: number;
}

/** The row archetype's win rate against the column archetype. */
export interface Matchup {
  row: string;
  col: string;
  win_rate: number;
  sample: number;
}

export interface ArchetypeCard {
  name: string;
  mana_cost: string;
  type: CardType;
  /** Percent of the archetype's lists. */
  inclusion: number;
  /** In the lists that run it. */
  avg_copies: number;
  /** Flex cards only: win rate and matches with and without the card. */
  win_rate_with?: number;
  sample_with?: number;
  win_rate_without?: number;
  sample_without?: number;
  /** Not in the design's types: the hover preview shows the card's price. */
  price_usd: number;
  price_tix: number;
}

export type EventKind = "challenge" | "league" | "paper";

export interface DeckSummary {
  id: string;
  /** The format's name as rankings uses it: "Modern", "EDH". */
  format: string;
  archetype_id: string;
  archetype: string;
  colors: Color[];
  player: string;
  event: string;
  event_kind: EventKind;
  online: boolean;
  /** ISO date. */
  date: string;
  players: number | null;
  /** "1st" | "2nd" | "3rd" | "Top 4" | "Top 8" | "Top 16" | "5-0" | "Trophy". */
  finish: string;
  /** 0 is the winner; leagues sort after Top 8. */
  finish_rank: number;
  /** "8-1"; cEDH "4-1-2" (W-L-D). */
  record: string;
  price_usd: number;
  price_tix: number;
}

export interface DeckCard {
  name: string;
  count: number;
  mana_cost: string;
  type: CardType;
  /** Unit prices. */
  price_usd: number;
  price_tix: number;
}

export interface DiffLine {
  zone: "main" | "side";
  name: string;
  delta: number;
}

export interface Decklist extends DeckSummary {
  /** Commander only. */
  commanders: DeckCard[];
  main: DeckCard[];
  sideboard: DeckCard[];
  diff_vs_average: DiffLine[];
}

/** An archetype's most common configuration, shown with the decklist view. */
export interface AverageList {
  format: string;
  archetype_id: string;
  archetype: string;
  colors: Color[];
  commanders: DeckCard[];
  main: DeckCard[];
  sideboard: DeckCard[];
  price_usd: number;
  price_tix: number;
}

/** A format as the metagame pages show it, with the rules that differ for cEDH. */
export interface MetagameFormat {
  /** The name rankings uses, and the value of the format search param: "Modern", "EDH". */
  format: string;
  /** The tab's name: "Modern", "Commander". */
  label: string;
  /** cEDH: four-player pods, a 25% baseline, Top 16, commanders and no sideboard. */
  multiplayer: boolean;
  /** Even win rate: 50, or 25 in a four-player pod. */
  baseline: number;
  /** The cut top_cut_lift measures: 8, or 16 in cEDH. */
  top_cut: number;
  /** Decklists in the default window, for the format tab. */
  decks: number;
}

export const METAGAME_WINDOWS = ["14", "30", "90", "bnr"] as const;
export type MetagameWindow = (typeof METAGAME_WINDOWS)[number];

export const METAGAME_SOURCES = ["all", "online", "paper"] as const;
export type MetagameSource = (typeof METAGAME_SOURCES)[number];

/** What every metagame response shares: its format, the format tabs and the window. */
export interface MetagameScope {
  format: MetagameFormat;
  /** Every format, in the design's tab order. */
  formats: MetagameFormat[];
  window: MetagameWindow;
  source: MetagameSource;
  /** ISO dates; the end is exclusive, as rankings windows are. */
  window_starts_on: string;
  window_ends_before: string;
  /** The last ban-and-restriction announcement, marked on the charts. */
  ban_date: string | null;
  /** The 14 weeks behind each series, as ISO start dates oldest → newest. */
  weeks: string[];
}

export interface ArchetypePage extends MetagameScope {
  decks: number;
  matches: number;
  events: number;
  /** Every archetype in the window by meta share; an archetype's rank is its index + 1. */
  archetypes: ArchetypeStat[];
  /** Each ordered pair of different archetypes; mirrors are left out. */
  matchups: Matchup[];
}

export type ArchetypeRef = Pick<ArchetypeStat, "id" | "name" | "colors">;

export interface ArchetypeMatchup {
  opponent: ArchetypeRef;
  win_rate: number;
  sample: number;
}

export interface ArchetypeDetail extends MetagameScope {
  /** Decklists in the window, across archetypes. */
  decks: number;
  archetype: ArchetypeStat;
  /** By meta share, from 1. */
  rank: number;
  /** Nonland cards in nearly every list, by copies. */
  core: ArchetypeCard[];
  /** Nonland cards in some lists, by inclusion, with win rates with and without. */
  flex: ArchetypeCard[];
  /** This archetype's matrix row, by the opponents' meta share. */
  matchups: ArchetypeMatchup[];
  /** Best finishes first, at most 8. */
  top_lists: DeckSummary[];
  average: AverageList;
}

export const DECK_EVENTS = ["challenge", "league", "paper"] as const;
export const DECK_FINISHES = ["top4", "winner"] as const;
export const DECK_SORTS = [
  "newest",
  "finish",
  "price_desc",
  "price_asc",
] as const;
export type DeckFinishFilter = (typeof DECK_FINISHES)[number];
export type DeckSort = (typeof DECK_SORTS)[number];

/** A decklist index row: the summary, plus the cards a card search matched in it. */
export interface DecklistRow extends DeckSummary {
  /** For a search of 3 or more characters, the matching cards and their copies. */
  card_matches: { name: string; count: number }[];
}

export interface DecklistQuery {
  q: string;
  colors: ColorChoice[];
  event: EventKind | null;
  archetype: string | null;
  finish: DeckFinishFilter | null;
  sort: DeckSort;
}

export interface DecklistPage extends MetagameScope {
  /** The lists that pass the filters, in the chosen order. */
  items: DecklistRow[];
  /** Every list in the pool, before filters. */
  total: number;
  /** Distinct events in the pool. */
  events: number;
  /** The format's archetypes, for the archetype select. */
  archetypes: ArchetypeRef[];
  /** The pool's first and last event dates, ISO. */
  first_date: string;
  last_date: string;
  /** The filters as applied, after normalizing the search params. */
  query: DecklistQuery;
}

export interface DecklistDetail {
  format: MetagameFormat;
  formats: MetagameFormat[];
  deck: Decklist;
}

/** Where a card stands in its format's current rankings, for the hover preview. */
export type CardRanking =
  | { status: "ranked"; rank: number; score: number | null }
  | { status: "unranked" }
  /** The rankings could not be read, so the preview says nothing about them. */
  | { status: "unknown" };

/** Everything the card hover preview shows. */
export interface PreviewCard {
  name: string;
  mana_cost: string;
  type: CardType;
  price_usd: number;
  price_tix: number;
  /** The catalog's scan of the card; null when the catalog has no match. */
  image: string | null;
  ranking: CardRanking;
}

/**
 * A decklist id names its format first: "modern.0.3", "edh.2.1". The format's name
 * as rankings uses it ("Modern", "EDH"), or null for an id outside the formats.
 */
export function deckFormatFromId(id: string): string | null {
  const prefix = id.split(".")[0].toLowerCase();
  return (
    designFormats.find(([, format]) => format.toLowerCase() === prefix)?.[1] ??
    null
  );
}

/** The finishes the site words, keyed as messages' metagame.finishes. */
const finishKeys: Record<string, keyof Messages["metagame"]["finishes"]> = {
  "1st": "first",
  "2nd": "second",
  "3rd": "third",
  "4th": "fourth",
  "5th": "fifth",
  "6th": "sixth",
  "7th": "seventh",
  "8th": "eighth",
  "Top 4": "top4",
  "Top 8": "top8",
  "Top 16": "top16",
  Trophy: "trophy",
};

/** A finish's message key, or null for one shown as published, such as a "5-0" record. */
export function finishKey(
  finish: string,
): keyof Messages["metagame"]["finishes"] | null {
  return finishKeys[finish] ?? null;
}
