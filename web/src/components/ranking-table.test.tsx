import { fireEvent, render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import type { Printing, RankedCard, RankingPage } from "@/lib/api";
import { router } from "@/test/navigation";
import { RankingTable, type SortLink } from "./ranking-table";

const constructed = {
  method_id: "constructed-score",
  method_version: "constructed-score-v1",
  label: "Constructed score",
  description: "Blends win rate, top-cut conversion and meta share.",
  outputs: ["score"],
  scored_cards: 200,
};
const volume = {
  method_id: "max-ratio",
  method_version: "max-ratio-v1",
  label: "Relative volume",
  description: "Decks with the card, against the most-played card.",
  outputs: ["max_ratio"],
  scored_cards: 200,
};

const run: RankingPage["score_run"] = {
  score_run_id: "run-1",
  source: "topdeck",
  format_name: "Modern",
  window_starts_on: "2025-10-01",
  window_ends_before: "2026-10-01",
  published_at: "2026-10-19T00:00:00Z",
  attribution: "Data provided by TopDeck.gg",
  events: 3,
  players: 9,
  decks: 7,
  top_cut_decks: 2,
  scored_cards: 200,
  matches: 12,
  players_per_game: 2,
  field_win_rate: 0.5,
  field_top_cut_rate: 0.25,
  series_starts_on: "2025-10-06",
  series_period_days: 30,
  series_decks: [0, 0, 0, 0, 0, 0, 0, 0, 0, 2, 0, 5],
  methods: [constructed, volume],
  components: null,
};

function printing(images: Printing["images"]): Printing {
  return {
    collector_number: "149",
    games: ["paper"],
    images,
    language: "en",
    rarity: "common",
    released_on: "2010-07-16",
    scryfall_id: "00000000-0000-0000-0000-000000000001",
    set_code: "m11",
    set_name: "Magic 2011",
    source_uri: "https://cards.example/m11/149",
  };
}

function card(overrides: Partial<RankedCard>): RankedCard {
  return {
    archetype_count: 2,
    archetype_deck_count: 3,
    archetype_label: "Burn",
    archetypes: [
      { label: "Burn", deck_count: 3, colors: ["R"] },
      { label: "Prowess", deck_count: 1, colors: ["U", "R"] },
    ],
    avg_copies: 3.75,
    color_identity: ["R"],
    deck_count: 4,
    event_count: 2,
    formats: null,
    games: 120,
    labelled_deck_count: 4,
    mana_cost: "{R}",
    name: "Lightning Bolt",
    oracle_id: "bolt",
    price_usd: 0.6,
    score_per_usd: 154.1666,
    preview_printing: printing([
      { face_index: null, artist: null, source_uri: "https://img/bolt.jpg" },
    ]),
    rank: 1,
    rank_change: 2,
    score: 92.5,
    series_decks: [0, 0, 0, 0, 0, 0, 0, 0, 0, 1, 0, 4],
    share_delta: 0.3,
    top_cut_count: 3,
    top_cut_known_decks: 4,
    top_cut_lift: 1.24,
    type_line: "Instant",
    win_rate: 0.55,
    win_rate_ci95: 0.04,
    win_rate_delta: 0.031,
    ...overrides,
  };
}

const bolt = card({});
const fire = card({
  oracle_id: "fire",
  name: "Fire // Ice",
  rank: 2,
  rank_change: -1,
  score: 40,
  deck_count: 2,
  event_count: 1,
  mana_cost: "{1}{R} // {1}{U}",
  type_line: "Instant // Instant",
  archetype_label: null,
  archetype_deck_count: 0,
  labelled_deck_count: 0,
  archetypes: [],
  archetype_count: 0,
  top_cut_count: null,
  top_cut_known_decks: 0,
  top_cut_lift: null,
  win_rate: null,
  win_rate_delta: null,
  win_rate_ci95: null,
  share_delta: null,
  price_usd: null,
  score_per_usd: null,
  preview_printing: printing([]),
});
const unlisted = card({
  oracle_id: "unlisted",
  name: "Synthetic Unlisted Card",
  rank: 3,
  rank_change: null,
  score: null,
  deck_count: 1,
  mana_cost: null,
  type_line: null,
  preview_printing: null,
});

const sorts: Record<string, SortLink> = {
  name: { href: "/rankings?sort=name", active: false, order: "asc" },
  score: { href: "/rankings?order=asc", active: true, order: "desc" },
  win_rate: { href: "/rankings?sort=win_rate", active: false, order: "desc" },
  decks: { href: "/rankings?sort=decks", active: false, order: "desc" },
  top_cut_lift: {
    href: "/rankings?sort=top_cut_lift",
    active: false,
    order: "desc",
  },
  trend: { href: "/rankings?sort=trend", active: false, order: "desc" },
  price: { href: "/rankings?sort=price", active: false, order: "desc" },
  value: { href: "/rankings?sort=value", active: false, order: "desc" },
};

function table(
  items: RankedCard[],
  { catalog = "snap-1" as string | null, method = constructed } = {},
) {
  return (
    <RankingTable
      items={items}
      run={run}
      method={method}
      graded={method === constructed}
      labels={{
        share: "Meta share",
        cut: "Top cut",
        trend: "12 mo",
        value: method === constructed ? "Grade per $" : "Score per $",
      }}
      sorts={sorts}
      maxDeckCount={8}
      catalogSnapshotId={catalog}
      pricesUpdatedAt="2026-09-27T21:05:46.301Z"
      clearHref="/rankings?format=Modern"
      footer={<p role="status">1–3 of 3 ranked cards</p>}
    />
  );
}

function row(name: RegExp): HTMLElement {
  return screen.getByRole("row", { name });
}

function cells(name: RegExp): HTMLElement[] {
  return within(row(name)).getAllByRole("cell");
}

function preview() {
  return within(screen.getByRole("complementary", { name: "Selected card" }));
}

describe("RankingTable", () => {
  it("heads each column, with the method behind an info tooltip", async () => {
    const user = userEvent.setup();
    render(table([bolt]));
    expect(
      screen.getAllByRole("columnheader").map((header) => header.textContent),
    ).toEqual([
      "#",
      "Card",
      expect.stringContaining("Grade"),
      expect.stringContaining("Price"),
      "Grade per $",
      "Win rate vs field",
      "Meta share",
      "Top cut",
      "Trend · 12 mo",
      "Most played in",
    ]);
    await user.hover(screen.getByRole("button", { name: "About this score" }));
    const tooltip = screen.getByRole("tooltip");
    expect(tooltip).toHaveTextContent("Method");
    expect(tooltip).toHaveTextContent(constructed.description);
    expect(tooltip).toHaveTextContent("constructed-score-v1");
  });

  it("sorts from the headers and marks the active one with its direction", () => {
    render(table([bolt]));
    const grade = screen.getByRole("columnheader", {
      name: /^Grade(?! per)/,
    });
    expect(grade).toHaveAttribute("aria-sort", "descending");
    expect(within(grade).getByRole("link")).toHaveTextContent("Grade ↓");
    expect(within(grade).getByRole("link")).toHaveAttribute(
      "href",
      "/rankings?order=asc",
    );
    expect(
      screen.getByRole("link", { name: "Win rate vs field" }),
    ).toHaveAttribute("href", "/rankings?sort=win_rate");
    expect(
      screen.getByRole("columnheader", { name: "Most played in" }),
    ).not.toHaveAttribute("aria-sort");
    expect(screen.queryByRole("link", { name: "Most played in" })).toBeNull();
  });

  it("shows rank and movement, the grade ring and each performance number", () => {
    const { container } = render(table([bolt, fire, unlisted]));
    const [rank, grade, , , win, share, cut, trend, archetype] =
      cells(/Lightning Bolt/);
    expect(rank).toHaveTextContent("1▲ 2Up 2 places");
    expect(within(grade).getByLabelText("Grade A+")).toHaveTextContent("A+");
    expect(grade).toHaveTextContent("92.5");
    expect(win).toHaveTextContent("+3.1% against the field");
    expect(win).toHaveTextContent("55.0% WR");
    expect(share).toHaveTextContent("57.1%");
    expect(cut).toHaveTextContent("1.24×");
    expect(cut.firstElementChild).toHaveClass("tone-positive");
    expect(trend.querySelector("svg path")).toHaveAttribute("d");
    expect(trend).toHaveTextContent("+30.0 points of meta share");
    expect(archetype).toHaveTextContent("Burn+1 more archetypes");
    expect(container.querySelector(".ring-a")).not.toBeNull();
    expect(
      within(row(/Lightning Bolt/))
        .getByRole("rowheader")
        .querySelector(".thumb img"),
    ).toHaveAttribute("src", "https://img/bolt.jpg");
  });

  it("keeps unknown numbers unknown rather than zero", () => {
    render(table([bolt, fire, unlisted]));
    const [rank, grade, , , win, , cut, trend, archetype] = cells(/Fire/);
    expect(rank).toHaveTextContent("▼ 1Down 1 place");
    expect(within(grade).getByLabelText("Grade D")).toBeInTheDocument();
    expect(win).toHaveTextContent("Unknown");
    expect(cut).toHaveTextContent("Unknown");
    expect(trend).toHaveTextContent("—");
    expect(archetype).toHaveTextContent("Unlabelled");
    expect(cells(/Unlisted/)[0]).toHaveTextContent("No earlier rank");
    expect(
      within(cells(/Unlisted/)[1]).getByLabelText("No grade"),
    ).toBeInTheDocument();
    expect(row(/Unlisted/)).toHaveTextContent("Not in this catalog");
  });

  it("reads a price the API omits as unknown, never NaN", () => {
    // An API from before prices sends neither field.
    const { price_usd: _price, score_per_usd: _value, ...unpriced } = bolt;
    render(table([unpriced as RankedCard]));
    const [, , price, value] = cells(/Lightning Bolt/);
    expect(price).toHaveTextContent("Unknown");
    expect(value).toHaveTextContent("Unknown");
    expect(preview().getByText("Price").nextElementSibling).toHaveTextContent(
      "Unknown",
    );
    expect(row(/Lightning Bolt/)).not.toHaveTextContent("NaN");
  });

  it("shows a plain score without grades for other methods", () => {
    render(table([bolt], { method: volume }));
    expect(
      screen.getByRole("columnheader", { name: /Relative volume/ }),
    ).toBeInTheDocument();
    expect(cells(/Lightning Bolt/)[1]).toHaveTextContent("92.5");
    expect(
      within(cells(/Lightning Bolt/)[1]).queryByLabelText(/Grade/),
    ).toBeNull();
  });

  it("heads unsortable columns plainly and an untimed trend without a reach", () => {
    render(
      <RankingTable
        items={[unlisted]}
        run={run}
        method={volume}
        graded={false}
        labels={{
          share: "Inclusion",
          cut: "Top cut",
          trend: null,
          value: "Score per $",
        }}
        sorts={{
          win_rate: {
            href: "/rankings?sort=win_rate&order=asc",
            active: true,
            order: "asc",
          },
        }}
        maxDeckCount={8}
        catalogSnapshotId="snap-1"
        pricesUpdatedAt={null}
        clearHref="/rankings?format=Modern"
        footer={null}
      />,
    );
    expect(
      screen.getByRole("columnheader", { name: "Trend" }),
    ).toBeInTheDocument();
    expect(screen.queryByRole("link", { name: "Card" })).toBeNull();
    expect(
      screen.getByRole("columnheader", { name: /Win rate vs field/ }),
    ).toHaveAttribute("aria-sort", "ascending");
    expect(
      screen.getByRole("link", { name: /Win rate vs field/ }),
    ).toHaveTextContent("Win rate vs field ↑");
    expect(cells(/Unlisted/)[1]).toHaveTextContent("Unknown");
    expect(preview().getByText("Inclusion")).toBeInTheDocument();
    expect(screen.queryByRole("link", { name: "Price" })).toBeNull();
    expect(
      screen.getByRole("columnheader", { name: "Score per $" }),
    ).toBeInTheDocument();
  });

  it("prices each card and its grade per dollar, unknown without a price", async () => {
    const user = userEvent.setup();
    render(table([bolt, fire]));
    const [, , price, value] = cells(/Lightning Bolt/);
    expect(price).toHaveTextContent("$0.60");
    expect(value).toHaveTextContent("154 per dollar");
    expect(cells(/Fire/)[2]).toHaveTextContent("Unknown");
    expect(cells(/Fire/)[3]).toHaveTextContent("Unknown");
    expect(screen.getByRole("link", { name: "Price" })).toHaveAttribute(
      "href",
      "/rankings?sort=price",
    );
    expect(screen.getByRole("link", { name: "Grade per $" })).toHaveAttribute(
      "href",
      "/rankings?sort=value",
    );
    expect(preview().getByText("Price").nextElementSibling).toHaveTextContent(
      "$0.60",
    );
    expect(
      preview().getByText("Grade per $").nextElementSibling,
    ).toHaveTextContent("154");
    await user.hover(screen.getByRole("button", { name: "About prices" }));
    expect(screen.getByRole("tooltip")).toHaveTextContent("As of Sep 27, 2026");
  });

  it("previews the leading label when the run names no archetype shares", () => {
    render(
      table([
        card({
          archetypes: [],
          win_rate_ci95: null,
          avg_copies: null,
          top_cut_lift: null,
        }),
      ]),
    );
    expect(preview().getByText("Burn")).toBeInTheDocument();
    expect(preview().getByText("75.0%")).toBeInTheDocument();
    expect(
      preview().getByText("Win rate").nextElementSibling,
    ).toHaveTextContent("55.0%");
    expect(
      preview().getByText("Top cut · copies").nextElementSibling,
    ).toHaveTextContent("— · —");
  });

  it("sizes share bars against the run's most-played card", () => {
    const { container } = render(table([bolt, fire]));
    const bars = [...container.querySelectorAll<HTMLElement>(".share-bar")];
    expect(bars.map((bar) => bar.style.getPropertyValue("--fill"))).toEqual([
      "50%",
      "25%",
    ]);
  });

  it("draws the thumbnail only where a scan exists", () => {
    render(table([fire, unlisted]));
    for (const name of [/Fire/, /Unlisted/])
      expect(row(name).querySelector(".thumb img")).toBeNull();
  });

  it("links cards in the joined catalog and leaves the others as text", () => {
    render(table([bolt, unlisted]));
    expect(
      within(row(/Lightning Bolt/)).getByRole("link", {
        name: "Lightning Bolt",
      }),
    ).toHaveAttribute("href", "/cards/bolt?catalog_snapshot_id=snap-1");
    expect(within(row(/Unlisted/)).queryByRole("link")).toBeNull();
    expect(row(/Unlisted/)).not.toHaveAttribute("data-opens");
  });

  it("previews the top card until a row is hovered or focused", async () => {
    const user = userEvent.setup();
    render(table([bolt, fire, unlisted]));
    expect(row(/Lightning Bolt/)).toHaveAttribute("data-selected", "true");
    expect(preview().getByText("Rank 1")).toBeInTheDocument();
    expect(preview().getByText("Up 2 places")).toBeInTheDocument();
    expect(
      preview().getByRole("img", {
        name: "Lightning Bolt — Magic 2011 #149 (EN)",
      }),
    ).toHaveAttribute("src", "https://img/bolt.jpg");
    expect(preview().getByLabelText("Grade A+")).toBeInTheDocument();
    expect(preview().getByText("92.5")).toBeInTheDocument();
    expect(preview().getByText("Top 1%")).toBeInTheDocument();
    expect(
      preview().getByText("Win rate").nextElementSibling,
    ).toHaveTextContent("55.0% ±4.0%");
    expect(
      preview().getByText("Vs field").nextElementSibling,
    ).toHaveTextContent("+3.1%");
    expect(
      preview().getByText("Meta share").nextElementSibling,
    ).toHaveTextContent("57.1%");
    expect(
      preview().getByText("Top cut · copies").nextElementSibling,
    ).toHaveTextContent("1.24× · 3.8");
    expect(preview().getByText("Burn")).toBeInTheDocument();
    expect(preview().getByText("75.0%")).toBeInTheDocument();
    expect(preview().getByText("Prowess")).toBeInTheDocument();
    expect(
      preview().getByRole("link", { name: "Open card: Lightning Bolt" }),
    ).toHaveAttribute("href", "/cards/bolt?catalog_snapshot_id=snap-1");

    await user.hover(row(/Fire/));
    expect(row(/Fire/)).toHaveAttribute("data-selected", "true");
    expect(row(/Lightning Bolt/)).not.toHaveAttribute("data-selected");
    expect(preview().getByText("Rank 2")).toBeInTheDocument();
    expect(
      preview().getByRole("img", {
        name: "Fire // Ice — Magic 2011 #149 (EN): image unavailable",
      }),
    ).toBeInTheDocument();
    expect(
      preview().getByText("Win rate").nextElementSibling,
    ).toHaveTextContent("—");
    expect(preview().getByText("No labelled decks")).toBeInTheDocument();

    fireEvent.focus(row(/Unlisted/));
    expect(preview().getByText("Rank 3")).toBeInTheDocument();
    expect(preview().getByText("Synthetic Unlisted Card")).toHaveClass(
      "preview-placeholder",
    );
    expect(preview().queryByRole("link")).toBeNull();
  });

  it("falls back to the top card when the selected one leaves the page", async () => {
    const user = userEvent.setup();
    const { rerender } = render(table([bolt, fire]));
    await user.hover(row(/Fire/));
    rerender(table([bolt, unlisted]));
    expect(preview().getByText("Rank 1")).toBeInTheDocument();
  });

  it("opens a card from anywhere on its row", async () => {
    const user = userEvent.setup();
    render(table([bolt]));
    await user.click(cells(/Lightning Bolt/)[2]);
    expect(router.push).toHaveBeenCalledExactlyOnceWith(
      "/cards/bolt?catalog_snapshot_id=snap-1",
    );
  });

  it("leaves the name link, text selection and unlisted cards alone", async () => {
    const user = userEvent.setup();
    render(table([bolt, unlisted]));
    const link = within(row(/Lightning Bolt/)).getByRole("link");
    link.addEventListener("click", (event) => event.preventDefault());
    await user.click(link);
    await user.click(row(/Unlisted/));
    vi.spyOn(window, "getSelection").mockReturnValue({
      toString: () => "Lightning",
    } as Selection);
    await user.click(cells(/Lightning Bolt/)[0]);
    expect(router.push).not.toHaveBeenCalled();
  });

  it("opens nothing without a joined catalog", async () => {
    const user = userEvent.setup();
    render(table([bolt], { catalog: null }));
    expect(within(row(/Lightning Bolt/)).queryByRole("link")).toBeNull();
    await user.click(row(/Lightning Bolt/));
    expect(router.push).not.toHaveBeenCalled();
  });

  it("grades the overall run by format instead of trend and archetype", async () => {
    const user = userEvent.setup();
    const overallGrade = {
      ...constructed,
      method_id: "overall-grade",
      method_version: "overall-grade-v1",
      label: "Overall grade",
    };
    const staple = card({
      win_rate: null,
      win_rate_ci95: null,
      win_rate_delta: 0.02,
      deck_count: 18235,
      archetypes: [],
      formats: [
        { format_name: "Legacy", score: 98.6 },
        { format_name: "EDH", score: 91 },
        { format_name: "Pauper", score: 72 },
        { format_name: "Modern", score: 40 },
      ],
    });
    render(
      <RankingTable
        items={[staple]}
        run={{
          ...run,
          format_name: "Overall",
          decks: 92506,
          components: Array.from({ length: 15 }, (_, index) => ({
            format_name: `Format ${index}`,
            score_run_id: `run-${index}`,
            decks: 100,
            weight: 0.3,
          })),
          methods: [overallGrade],
        }}
        method={overallGrade}
        graded
        labels={{
          share: "Decklists",
          cut: "Top cut",
          trend: null,
          value: "Grade per $",
        }}
        sorts={sorts}
        maxDeckCount={18235}
        catalogSnapshotId="snap-1"
        pricesUpdatedAt={null}
        clearHref="/rankings?format=Overall"
        footer={null}
      />,
    );
    expect(
      screen.getAllByRole("columnheader").map((header) => header.textContent),
    ).toEqual([
      "#",
      "Card",
      expect.stringContaining("Grade"),
      expect.stringContaining("Price"),
      "Grade per $",
      "Vs field",
      "Decklists",
      "Top cut",
      "Graded in",
    ]);
    const [, , , , vsField, decklists, , graded] = cells(/Lightning Bolt/);
    // Only the gap to each format's own field is pooled, so no raw win rate shows.
    expect(vsField).toHaveTextContent("+2.0%");
    expect(vsField).not.toHaveTextContent("WR");
    expect(decklists).toHaveTextContent("18,235");
    expect(graded).toHaveTextContent("LegacyA+CommanderA++2 more formats");
    await user.hover(row(/Lightning Bolt/));
    expect(preview().getByText("Graded in")).toBeInTheDocument();
    expect(preview().getByText("Modern")).toBeInTheDocument();
    expect(preview().getByText("Formats").nextSibling).toHaveTextContent(
      "4 of 15",
    );
  });

  it("explains an empty page inside the table and drops the preview", () => {
    render(table([]));
    expect(
      screen.getByRole("heading", { level: 3, name: "No ranked cards match." }),
    ).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Clear filters" })).toHaveAttribute(
      "href",
      "/rankings?format=Modern",
    );
    expect(screen.queryByRole("complementary")).toBeNull();
    expect(screen.getByRole("status")).toHaveTextContent("1–3 of 3");
  });
});
