import { describe, expect, it } from "vitest";
import type { DeckCard } from "./api";
import { copies, deckGroup, groupCards } from "./deck-groups";

function card(name: string, type_line: string | null, count = 1): DeckCard {
  return {
    oracle_id: name,
    name,
    copies: count,
    mana_cost: null,
    type_line,
    mana_value: null,
    in_catalog: type_line !== null,
  };
}

describe("deckGroup", () => {
  it.each([
    ["Creature — Goblin", "creature"],
    ["Artifact Creature — Golem", "creature"],
    ["Land Creature — Forest Dryad", "creature"],
    ["Artifact Land", "land"],
    ["Legendary Planeswalker — Jace", "planeswalker"],
    ["Battle — Siege", "battle"],
    ["Kindred Instant — Elf", "instant"],
    ["Instant // Land", "instant"],
    ["Sorcery", "sorcery"],
    ["Legendary Artifact", "artifact"],
    ["Enchantment — Saga", "enchantment"],
    ["Dungeon", "misc"],
    [null, "misc"],
  ])("puts %s with the %s cards", (typeLine, group) => {
    expect(deckGroup(typeLine)).toBe(group);
  });
});

describe("groupCards", () => {
  it("reads creatures first and lands last, leaving empty groups out", () => {
    const groups = groupCards([
      card("Mountain", "Basic Land — Mountain", 18),
      card("Lightning Bolt", "Instant", 4),
      card("Goblin Guide", "Creature — Goblin Scout", 4),
      card("Fireblast", "Instant", 2),
      card("Unknown", null),
    ]);

    expect(groups.map(({ group, count }) => [group, count])).toEqual([
      ["creature", 4],
      ["instant", 6],
      ["land", 18],
      ["misc", 1],
    ]);
    expect(groups[1].cards.map((each) => each.name)).toEqual([
      "Lightning Bolt",
      "Fireblast",
    ]);
  });

  it("counts a list's copies", () => {
    expect(copies([card("A", "Instant", 4), card("B", "Land", 3)])).toBe(7);
    expect(copies([])).toBe(0);
  });
});
