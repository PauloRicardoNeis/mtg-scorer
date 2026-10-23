import { render, screen, within } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import type { DeckCard } from "@/lib/api";
import { DeckZone } from "./deck-list";

const BOLT = "4457ed35-7c10-48c8-9776-456485fdf070";

function card(overrides: Partial<DeckCard>): DeckCard {
  return {
    oracle_id: BOLT,
    name: "Lightning Bolt",
    copies: 4,
    mana_cost: "{R}",
    type_line: "Instant",
    mana_value: 1,
    in_catalog: true,
    ...overrides,
  };
}

const MAIN = [
  card({}),
  card({
    oracle_id: "mountain",
    name: "Mountain",
    copies: 18,
    mana_cost: null,
    type_line: "Basic Land — Mountain",
  }),
  card({
    oracle_id: "unlisted",
    name: "Synthetic Unlisted Card",
    copies: 2,
    mana_cost: null,
    type_line: null,
    in_catalog: false,
  }),
];

describe("DeckZone", () => {
  it("heads a grouped zone with its copies and reads it by type", () => {
    render(
      <DeckZone title="Main deck" cards={MAIN} catalog="catalog-a" grouped />,
    );
    const zone = screen.getByRole("region", { name: "Main deck" });

    expect(within(zone).getByRole("heading", { level: 2 })).toHaveTextContent(
      "Main deck 24 cards",
    );
    expect(
      within(zone)
        .getAllByRole("heading", { level: 3 })
        .map((heading) => heading.textContent),
    ).toEqual(["Instants 4", "Lands 18", "Other cards 2"]);
  });

  it("links the cards the catalog has, in that catalog, and marks the card the reader came from", () => {
    render(
      <DeckZone
        title="Main deck"
        cards={MAIN}
        catalog="catalog-a"
        fromCard={BOLT}
      />,
    );
    const bolt = screen.getByRole("link", { name: "Lightning Bolt" });

    expect(bolt).toHaveAttribute(
      "href",
      `/cards/${BOLT}?catalog_snapshot_id=catalog-a`,
    );
    expect(bolt.closest("li")).toHaveClass("from-card");
    expect(bolt.closest("li")).toHaveTextContent(
      "4Lightning Bolt (the card you came from)",
    );
    expect(
      screen.queryByRole("link", { name: "Synthetic Unlisted Card" }),
    ).not.toBeInTheDocument();
    expect(
      screen.getByText("Synthetic Unlisted Card").closest("li"),
    ).not.toHaveClass("from-card");
    expect(screen.queryAllByRole("heading", { level: 3 })).toHaveLength(0);
  });

  it("names a single copy in the heading", () => {
    render(
      <DeckZone
        title="Commander"
        cards={[card({ copies: 1 })]}
        catalog="catalog-a"
      />,
    );

    expect(screen.getByRole("heading", { level: 2 })).toHaveTextContent(
      "Commander 1 card",
    );
  });
});
