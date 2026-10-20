import { render, screen, within } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import type { ComparedCard, ComparePage } from "@/lib/api";
import {
  CompareTable,
  type CompareSort,
  type CompareStat,
} from "./compare-table";

function cell(overrides: Partial<ComparedCard["formats"][string]> = {}) {
  return {
    rank: 1,
    score: 92.5,
    win_rate_delta: 0.06,
    share: 0.3,
    top_cut_lift: 1.2,
    share_delta: 0.02,
    ...overrides,
  };
}

const bolt: ComparedCard = {
  oracle_id: "bolt",
  name: "Lightning Bolt",
  mana_cost: "{R}",
  type_line: "Instant",
  color_identity: ["R"],
  ranked_in: 3,
  best_format: "EDH",
  best_score: 92.5,
  formats: {
    EDH: cell(),
    Modern: cell({
      rank: 40,
      score: 30,
      win_rate_delta: -0.04,
      share: 0.01,
      top_cut_lift: 0.9,
      share_delta: -0.02,
    }),
    Legacy: cell({
      score: 60,
      win_rate_delta: 0,
      share_delta: 0.001,
      top_cut_lift: null,
    }),
  },
};
const unlisted: ComparedCard = {
  oracle_id: "unlisted",
  name: "Synthetic Unlisted Card",
  mana_cost: null,
  type_line: null,
  color_identity: null,
  ranked_in: 1,
  best_format: "Modern",
  best_score: null,
  formats: {
    Modern: cell({
      score: null,
      win_rate_delta: null,
      share: null,
      top_cut_lift: null,
      share_delta: null,
    }),
  },
};

const page: ComparePage = {
  formats: [
    { format_name: "EDH", score_run_id: "a", decks: 100, players_per_game: 4 },
    {
      format_name: "Modern",
      score_run_id: "b",
      decks: 50,
      players_per_game: 2,
    },
    {
      format_name: "Legacy",
      score_run_id: "c",
      decks: 50,
      players_per_game: null,
    },
  ],
  available: [],
  catalog_snapshot_id: null,
  total: 1234,
  offset: 0,
  limit: 50,
  sort: "Modern:grade",
  order: "asc",
  every: false,
  items: [bolt, unlisted],
};

const sorts = (key: string): CompareSort => ({
  href: `/rankings/compare?sort=${key}`,
  active: key === "Modern:grade",
  order: key === "Modern:grade" ? "asc" : "desc",
});

function table(
  stats: CompareStat[],
  items = page.items,
  summaries: ("best" | "count")[] = ["best", "count"],
) {
  return (
    <CompareTable
      page={{ ...page, items }}
      stats={stats}
      summaries={summaries}
      sorts={sorts}
      footer={<p role="status">1–2 of 1,234 cards</p>}
    />
  );
}

function row(name: RegExp) {
  return screen.getByRole("row", { name });
}

describe("CompareTable", () => {
  it("groups each format's stats under a link to its rankings", () => {
    render(table(["grade", "share"]));
    const groups = screen.getAllByRole("columnheader", {
      name: /Commander|Modern|Legacy|Summary/,
    });
    expect(groups[0]).toHaveAttribute("colspan", "2");
    expect(screen.getByRole("link", { name: "Commander" })).toHaveAttribute(
      "href",
      "/rankings?format=EDH",
    );
    expect(screen.getByText("1,234 cards")).toBeInTheDocument();
    // Pods count inclusion, one-on-one formats meta share.
    expect(
      screen
        .getAllByRole("link", { name: /^(Inclusion|Share)/ })
        .map((l) => l.textContent),
    ).toEqual(["Inclusion", "Share", "Share"]);
  });

  it("sorts from every metric header and marks the active one", () => {
    render(table(["grade"]));
    const active = screen
      .getAllByRole("columnheader")
      .find((h) => h.getAttribute("aria-sort"));
    expect(active).toHaveAttribute("aria-sort", "ascending");
    expect(within(active!).getByRole("link")).toHaveTextContent("Grade ↑");
    expect(screen.getByRole("link", { name: "Card" })).toHaveAttribute(
      "href",
      "/rankings/compare?sort=name",
    );
    expect(screen.getByRole("link", { name: "Best format" })).toHaveAttribute(
      "href",
      "/rankings/compare?sort=best",
    );
  });

  it("tints grade and score cells that stand out and keeps the middle plain", () => {
    render(table(["grade", "score"]));
    const [edhGrade, edhScore, modernGrade, , legacyGrade] = within(
      row(/Lightning Bolt/),
    ).getAllByRole("cell");
    expect(edhGrade).toHaveClass("heat-up");
    expect(edhGrade.style.getPropertyValue("--tint")).toBe("0.206");
    expect(within(edhGrade).getByLabelText("Grade A+")).toBeInTheDocument();
    expect(edhScore).toHaveTextContent("92.5");
    expect(modernGrade).toHaveClass("heat-down");
    expect(modernGrade.style.getPropertyValue("--tint")).toBe("0.160");
    expect(legacyGrade.className).not.toMatch(/heat/);
  });

  it("tones win rate, share, lift and trend cells", () => {
    render(table(["win_rate", "share", "top_cut_lift", "trend"]));
    const cells = within(row(/Lightning Bolt/)).getAllByRole("cell");
    const [
      edhWin,
      edhShare,
      edhLift,
      edhTrend,
      modernWin,
      ,
      modernLift,
      modernTrend,
      legacyWin,
      ,
      legacyLift,
      legacyTrend,
    ] = cells;
    expect(edhWin).toHaveTextContent("+6.0%");
    expect(edhWin).toHaveClass("heat-up");
    expect(edhShare).toHaveTextContent("30.0%");
    expect(edhShare).toHaveClass("heat-share");
    expect(edhLift.firstElementChild).toHaveClass("tone-positive");
    expect(edhTrend.firstElementChild).toHaveClass("tone-positive");
    expect(modernWin).toHaveClass("heat-down");
    expect(modernLift.firstElementChild).toHaveClass("tone-negative");
    expect(modernTrend.firstElementChild).toHaveClass("tone-negative");
    expect(legacyWin.className).not.toMatch(/heat/);
    expect(legacyLift).toHaveTextContent("—");
    expect(legacyTrend.firstElementChild).toHaveClass("tone-neutral");
  });

  it("dashes the formats that do not rank a card and the numbers it lacks", () => {
    render(
      table(["grade", "score", "win_rate", "share", "top_cut_lift", "trend"]),
    );
    const cells = within(row(/Unlisted/)).getAllByRole("cell");
    expect(cells[0]).toHaveClass("unranked");
    expect(cells[0]).toHaveAttribute("title", "Not ranked in Commander");
    const modern = cells.slice(6, 12);
    expect(within(modern[0]).getByLabelText("No grade")).toBeInTheDocument();
    expect(modern.slice(1).map((c) => c.textContent)).toEqual([
      "—",
      "—",
      "—",
      "—",
      "—",
    ]);
    expect(row(/Unlisted/)).toHaveTextContent("Not in this catalog");
  });

  it("summarizes the best format and how many formats rank the card", () => {
    render(table(["grade"]));
    const bestCells = within(row(/Lightning Bolt/)).getAllByRole("cell");
    expect(bestCells.at(-2)).toHaveTextContent("CommanderA+");
    expect(bestCells.at(-1)).toHaveTextContent("3 / 3");
    expect(bestCells.at(-1)).not.toHaveClass("muted");
    const unlistedCells = within(row(/Unlisted/)).getAllByRole("cell");
    expect(unlistedCells.at(-2)).toHaveTextContent("Modern");
    expect(unlistedCells.at(-1)).toHaveClass("muted");
  });

  it("marks a descending sort with a down arrow", () => {
    render(
      <CompareTable
        page={page}
        stats={["grade"]}
        summaries={["best"]}
        sorts={(key) => ({ href: "#", active: key === "best", order: "desc" })}
        footer={null}
      />,
    );
    const best = screen.getByRole("columnheader", { name: /Best format/ });
    expect(best).toHaveAttribute("aria-sort", "descending");
    expect(best).toHaveTextContent("Best format ↓");
  });

  it("leaves the summary out when none is chosen", () => {
    render(table(["grade"], page.items, []));
    expect(screen.queryByRole("columnheader", { name: "Summary" })).toBeNull();
  });

  it("explains an empty comparison and keeps the legend", () => {
    render(table(["grade"], []));
    expect(
      screen.getByRole("heading", { level: 3, name: "No cards match." }),
    ).toBeInTheDocument();
    expect(
      screen.getByText("Tinted cells stand out in that format"),
    ).toBeInTheDocument();
    expect(screen.getByRole("status")).toHaveTextContent("1–2 of 1,234 cards");
  });
});
