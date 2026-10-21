import type { DeckCard } from "./api";

/** A decklist's groups in the order they read: creatures first, lands last. */
export const DECK_GROUPS = [
  "creature",
  "planeswalker",
  "battle",
  "instant",
  "sorcery",
  "artifact",
  "enchantment",
  "land",
  "misc",
] as const;

export type DeckGroup = (typeof DECK_GROUPS)[number];

// Which type wins when a card has several: an artifact creature is a creature and an
// artifact land a land, as decklists usually show them.
const PRECEDENCE: DeckGroup[] = [
  "creature",
  "land",
  "planeswalker",
  "battle",
  "instant",
  "sorcery",
  "artifact",
  "enchantment",
];

/**
 * A card's group by its front face's types, before the subtype dash: "Instant // Land" is an
 * instant. A card the catalog does not have, or of no listed type, is "misc".
 */
export function deckGroup(typeLine: string | null): DeckGroup {
  if (!typeLine) return "misc";
  const types = typeLine.split(" // ")[0].split("—")[0].toLowerCase();
  const words = new Set(types.split(/\s+/));
  return PRECEDENCE.find((group) => words.has(group)) ?? "misc";
}

export type GroupedCards = {
  group: DeckGroup;
  cards: DeckCard[];
  count: number;
};

/** A list's cards by group, in reading order, each group with its copies; empty groups are left out. */
export function groupCards(cards: DeckCard[]): GroupedCards[] {
  return DECK_GROUPS.map((group) => {
    const members = cards.filter((card) => deckGroup(card.type_line) === group);
    return { group, cards: members, count: copies(members) };
  }).filter((entry) => entry.cards.length > 0);
}

/** The copies a list holds, as a deck counts its cards. */
export function copies(cards: DeckCard[]): number {
  return cards.reduce((total, card) => total + card.copies, 0);
}
