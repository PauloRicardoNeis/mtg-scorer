import { render, screen, within } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import type { CardDeck, CardDeckPage } from "@/lib/api";
import { CardDecks } from "./card-decks";

const BOLT = "4457ed35-7c10-48c8-9776-456485fdf070";
const MODERN = `scores-${"a".repeat(64)}`;
const LEGACY = `scores-${"b".repeat(64)}`;
const PATH = `/cards/${BOLT}`;

function deck(overrides: Partial<CardDeck> = {}): CardDeck {
  return {
    position: 0,
    source_deck_id: "modern-10k#10",
    event: {
      source_event_id: "modern-10k",
      name: "Modern 10K",
      url: "https://topdeck.gg/bracket/modern-10k",
      occurred_on: "2026-08-30",
      players: 13,
    },
    archetype: "Burn",
    copies: 4,
    final_rank: null,
    made_top_cut: true,
    wins: 3,
    losses: 1,
    draws: 2,
    ...overrides,
  };
}

function page(overrides: Partial<CardDeckPage> = {}): CardDeckPage {
  return {
    oracle_id: BOLT,
    formats: [
      {
        format_name: "Modern",
        source: "topdeck",
        score_run_id: MODERN,
        deck_count: 118,
      },
      {
        format_name: "Legacy",
        source: "topdeck",
        score_run_id: LEGACY,
        deck_count: 1,
      },
    ],
    run: {
      score_run_id: MODERN,
      source: "topdeck",
      format_name: "Modern",
      window_starts_on: "2024-01-01",
      window_ends_before: "2026-10-01",
      attribution: "Data provided by TopDeck.gg (https://topdeck.gg)",
    },
    total: 118,
    offset: 0,
    limit: 20,
    items: [deck()],
    ...overrides,
  };
}

function show(value: CardDeckPage, query = "catalog_snapshot_id=catalog-a") {
  return render(
    <CardDecks page={value} path={PATH} query={new URLSearchParams(query)} />,
  );
}

describe("CardDecks", () => {
  it("offers a tab per format with its decks, marking the run shown", () => {
    show(page());
    const tabs = within(
      screen.getByRole("navigation", { name: "Deck formats" }),
    ).getAllByRole("link");

    expect(tabs.map((tab) => tab.textContent)).toEqual([
      "Modern118",
      "Legacy1",
    ]);
    expect(tabs[0]).toHaveAttribute("aria-current", "page");
    expect(tabs[1]).toHaveAttribute(
      "href",
      `${PATH}?catalog_snapshot_id=catalog-a&decks_run=${LEGACY}#decks`,
    );
  });

  it("lists each deck's event, archetype, copies and result", () => {
    show(page());
    const item = screen.getByRole("listitem");

    expect(
      within(item).getByRole("link", { name: /^Modern 10K \(opens new tab\)/ }),
    ).toHaveAttribute("href", "https://topdeck.gg/bracket/modern-10k");
    expect(item).toHaveTextContent("Aug 30, 2026 · 13 players");
    expect(
      within(item).getByRole("link", {
        name: "Open the Burn deck from Modern 10K",
      }),
    ).toHaveAttribute(
      "href",
      `/decks/${MODERN}/0?card=${BOLT}&catalog_snapshot_id=catalog-a`,
    );
    expect(item).toHaveTextContent("4 copies in the main deck");
    expect(
      within(item).getByTitle("Match record: wins, losses, draws"),
    ).toHaveTextContent("3–1–2");
    expect(within(item).getByText("Top cut")).toHaveClass("badge");
    expect(screen.getByText(/1–1 of 118 decks/)).toHaveTextContent(
      "Events Jan 1, 2024 – Sep 30, 2026 · Data provided by TopDeck.gg",
    );
  });

  it("names an unnamed, unlinked, unlabelled deck by what is known", () => {
    show(
      page({
        items: [
          deck({
            event: {
              source_event_id: "ptsyn05",
              name: null,
              url: null,
              occurred_on: "2005-10-28",
              players: null,
            },
            archetype: null,
            copies: 1,
            final_rank: 3,
            made_top_cut: null,
            wins: null,
            losses: null,
            draws: null,
          }),
        ],
      }),
    );
    const item = screen.getByRole("listitem");

    expect(
      within(item).queryByRole("link", { name: /opens new tab/ }),
    ).not.toBeInTheDocument();
    expect(
      within(item).getByRole("link", {
        name: "Open the Unlabelled deck from ptsyn05",
      }),
    ).toHaveTextContent("Unlabelled");
    expect(within(item).getByRole("heading")).toHaveTextContent("ptsyn05");
    expect(item).toHaveTextContent("Oct 28, 2005");
    expect(item).not.toHaveTextContent("players");
    expect(item).toHaveTextContent("Unlabelled");
    expect(item).toHaveTextContent("1 copy in the main deck");
    expect(item).toHaveTextContent("No record");
    expect(within(item).getByText("#3")).toHaveClass("badge");
    expect(within(item).queryByText("Top cut")).not.toBeInTheDocument();
  });

  it("pages through the run, keeping the rest of the query", () => {
    show(
      page({ offset: 20, items: [deck({ position: 20 })] }),
      `catalog_snapshot_id=catalog-a&decks_run=${MODERN}&decks_offset=20`,
    );
    const pages = within(
      screen.getByRole("navigation", { name: "Deck pages" }),
    );

    expect(pages.getByRole("link", { name: /Previous decks/ })).toHaveAttribute(
      "href",
      `${PATH}?catalog_snapshot_id=catalog-a&decks_run=${MODERN}#decks`,
    );
    expect(pages.getByRole("link", { name: /More decks/ })).toHaveAttribute(
      "href",
      `${PATH}?catalog_snapshot_id=catalog-a&decks_run=${MODERN}&decks_offset=40#decks`,
    );
  });

  it("offers no pages when every deck fits on one", () => {
    show(page({ total: 1 }));

    expect(
      screen.queryByRole("navigation", { name: "Deck pages" }),
    ).not.toBeInTheDocument();
  });

  it("says so when no published deck played the card", () => {
    show(page({ formats: [], run: null, total: 0, items: [] }));

    expect(
      screen.getByText("No published tournament deck played this card."),
    ).toBeInTheDocument();
    expect(screen.queryByRole("navigation")).not.toBeInTheDocument();
  });

  it("says so when the run shown has no decks on this page", () => {
    show(page({ total: 3, offset: 20, items: [] }));

    expect(
      screen.getByText("No decks with this card on this page."),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("link", { name: /Previous decks/ }),
    ).toBeInTheDocument();
  });
});
