import { fireEvent, render, screen, within } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import type { CommanderPage, Printing, RankedCommander } from "@/lib/api";
import { CommanderTable } from "./commander-table";
import type { SortLink } from "./ranking-table";

const run: CommanderPage["score_run"] = {
  score_run_id: "run-1",
  source: "topdeck",
  format_name: "EDH",
  window_starts_on: "2025-10-01",
  window_ends_before: "2026-10-01",
  published_at: "2026-10-20T00:00:00Z",
  attribution: "Data provided by TopDeck.gg",
  events: 3,
  players: 40,
  decks: 40,
  top_cut_decks: 8,
  scored_cards: 900,
  matches: 60,
  players_per_game: 4,
  field_win_rate: 0.25,
  field_top_cut_rate: 0.2,
  series_starts_on: "2025-10-06",
  series_period_days: 30,
  series_decks: [0, 0, 0, 0, 0, 0, 0, 0, 0, 10, 10, 20],
  methods: [],
  components: null,
};

function printing(uri: string): Printing {
  return {
    collector_number: "1",
    games: ["paper"],
    images: [{ face_index: null, artist: null, source_uri: uri }],
    language: "en",
    rarity: "mythic",
    released_on: "2020-01-01",
    scryfall_id: "00000000-0000-0000-0000-000000000001",
    set_code: "cmr",
    set_name: "Commander Legends",
    source_uri: "https://cards.example/cmr/1",
  };
}

function card(
  oracle_id: string,
  name: string,
  overrides: Partial<RankedCommander["commanders"][number]> = {},
): RankedCommander["commanders"][number] {
  return {
    oracle_id,
    name,
    mana_cost: "{G}{U}",
    type_line: "Legendary Creature — Human Druid",
    color_identity: ["G", "U"],
    preview_printing: printing(`https://img/${oracle_id}.jpg`),
    ...overrides,
  };
}

function commander(overrides: Partial<RankedCommander>): RankedCommander {
  return {
    rank: 1,
    rank_change: 2,
    label: "Kinnan, Bonder Prodigy",
    commanders: [card("kinnan", "Kinnan, Bonder Prodigy")],
    colors: ["U", "G"],
    deck_count: 12,
    event_count: 3,
    top_cut_count: 4,
    top_cut_known_decks: 12,
    win_rate: 0.29,
    win_rate_delta: 0.04,
    win_rate_ci95: 0.05,
    games: 60,
    top_cut_lift: 1.67,
    share_delta: 0.05,
    series_decks: [0, 0, 0, 0, 0, 0, 0, 0, 0, 2, 3, 7],
    core_card_count: 71,
    ...overrides,
  };
}

const kinnan = commander({});
const pair = commander({
  rank: 2,
  rank_change: null,
  label: "Kraum, Ludevic's Opus + Tymna the Weaver",
  commanders: [
    card("kraum", "Kraum, Ludevic's Opus", { type_line: "Legendary Creature" }),
    card("tymna", "Tymna the Weaver", { preview_printing: null }),
  ],
  colors: ["W", "U", "B", "R"],
  deck_count: 8,
  win_rate: null,
  win_rate_delta: null,
  win_rate_ci95: null,
  top_cut_count: null,
  top_cut_known_decks: 0,
  top_cut_lift: null,
  core_card_count: 1,
});

const sorts: Record<string, SortLink> = Object.fromEntries(
  ["name", "decks", "win_rate", "top_cut_lift", "trend"].map((key) => [
    key,
    {
      href: `/rankings/commanders?sort=${key}`,
      active: key === "decks",
      order: key === "name" ? "asc" : "desc",
    },
  ]),
);

function table(items: RankedCommander[], catalog: string | null = "snap-1") {
  return (
    <CommanderTable
      items={items}
      run={run}
      sorts={sorts}
      shareLabel="Meta share"
      trendLabel="12 mo"
      maxDeckCount={12}
      catalogSnapshotId={catalog}
      clearHref="/rankings/commanders?format=EDH"
      footer={<p role="status">1–2 of 2 commanders</p>}
    />
  );
}

function preview() {
  return within(
    screen.getByRole("complementary", { name: "Selected commander" }),
  );
}

describe("CommanderTable", () => {
  it("heads each column, sorting by decks", () => {
    render(table([kinnan, pair]));

    expect(
      screen.getAllByRole("columnheader").map((header) => header.textContent),
    ).toEqual([
      "#",
      "Commander",
      "Meta share ↓",
      "Win rate vs field",
      "Top cut",
      "Trend · 12 mo",
      "Events",
    ]);
    expect(
      screen.getByRole("columnheader", { name: /Meta share/ }),
    ).toHaveAttribute("aria-sort", "descending");
  });

  it("names a partner pair's commanders apart, each linked to its card", () => {
    render(table([kinnan, pair]));
    const row = screen.getByRole("row", { name: /Tymna the Weaver/ });

    expect(
      within(row).getByRole("link", { name: "Kraum, Ludevic's Opus" }),
    ).toHaveAttribute("href", "/cards/kraum?catalog_snapshot_id=snap-1");
    // Tymna is not in the catalog, so its name has no card to open.
    expect(
      within(row).queryByRole("link", { name: "Tymna the Weaver" }),
    ).toBeNull();
    expect(within(row).getByText("Tymna the Weaver")).toBeInTheDocument();
    // A pair spans two cards' types, so the row shows none.
    expect(within(row).queryByText("Legendary Creature")).toBeNull();
    const cells = within(row).getAllByRole("cell");
    expect(cells[1]).toHaveTextContent("20.0%");
    expect(cells[2]).toHaveTextContent("Unknown");
    expect(cells[3]).toHaveTextContent("Unknown");
  });

  it("previews the top commander, then the one a reader points at", () => {
    render(table([kinnan, pair]));

    expect(preview().getByText("Rank 1")).toBeInTheDocument();
    expect(preview().getByText("29.0%")).toBeInTheDocument();
    expect(preview().getByText("+4.0%")).toBeInTheDocument();
    expect(preview().getByText("1.67×")).toBeInTheDocument();
    expect(
      preview().getByText("71 cards in most of its decks"),
    ).toBeInTheDocument();
    expect(
      preview().getByRole("link", {
        name: "Open card: Kinnan, Bonder Prodigy",
      }),
    ).toHaveTextContent("Open card");

    fireEvent.pointerEnter(screen.getByRole("row", { name: /Tymna/ }));

    expect(preview().getByText("Rank 2")).toBeInTheDocument();
    expect(
      preview().getByText("1 card in most of its decks"),
    ).toBeInTheDocument();
    // Each partner gets its own button, named for its card; Tymna has no card page.
    expect(
      preview()
        .getAllByRole("link")
        .map((link) => link.textContent),
    ).toEqual(["Kraum, Ludevic's Opus"]);
    expect(preview().getByText("Tymna the Weaver")).toBeInTheDocument();
  });

  it("offers to clear filters when no commander matches", () => {
    render(table([]));

    expect(screen.getByText("No commanders match.")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Clear filters" })).toHaveAttribute(
      "href",
      "/rankings/commanders?format=EDH",
    );
    expect(screen.queryByRole("complementary")).toBeNull();
  });
});
