import { fireEvent, render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";
import { router } from "@/test/navigation";
import { RankingFilters } from "./ranking-filters";

const clearHref = "/rankings?format=Modern&score_run_id=run-1";

const views = [
  {
    view: "all",
    label: "All",
    count: 608,
    href: "/rankings?all",
    current: true,
  },
  {
    view: "risers",
    label: "Risers",
    count: 40,
    href: "/rankings?risers",
    current: false,
  },
  {
    view: "fallers",
    label: "Fallers",
    count: 1234,
    href: "/rankings?fallers",
    current: false,
  },
];

function filters(query = "") {
  return (
    <RankingFilters
      format="Modern"
      scoreRunId="run-1"
      query={query}
      clearHref={clearHref}
      views={views}
    />
  );
}

function select(name: string): HTMLSelectElement {
  return screen.getByRole("combobox", { name });
}

/** The query of the address the filters replaced, as pairs. */
function replaced(): [string, string][] {
  expect(router.replace).toHaveBeenCalledTimes(1);
  const [href, options] = router.replace.mock.calls[0];
  expect(options).toEqual({ scroll: false });
  const url = new URL(String(href), location.origin);
  expect(url.pathname).toBe("/rankings");
  return [...url.searchParams];
}

describe("RankingFilters", () => {
  it("names each control for assistive tech without visible labels", () => {
    render(filters());
    const form = screen.getByRole("form", { name: "Ranking filters" });
    expect(form).toHaveAttribute("action", "/rankings");
    // Without JavaScript the form still submits as a plain GET.
    expect(form).toHaveAttribute("method", "get");
    expect(screen.getByRole("group", { name: "Colors" })).toBeInTheDocument();
    expect(screen.getByText("Colors")).toHaveClass("sr-only");
    expect(select("Card type")).toHaveValue("");
    // Sorting moved to the table's headers.
    expect(screen.queryByRole("combobox", { name: "Sort by" })).toBeNull();
    expect(screen.queryByRole("link", { name: "Clear filters" })).toBeNull();
  });

  it("shows every view with its count and marks the current one", () => {
    render(filters());
    const tabs = within(screen.getByRole("navigation", { name: "Views" }));
    expect(tabs.getAllByRole("link").map((tab) => tab.textContent)).toEqual([
      "All608",
      "Risers40",
      "Fallers1,234",
    ]);
    expect(tabs.getByRole("link", { name: /All/ })).toHaveAttribute(
      "aria-current",
      "page",
    );
    expect(tabs.getByRole("link", { name: /Risers/ })).toHaveAttribute(
      "href",
      "/rankings?risers",
    );
  });

  it("reflects the filters in the query", () => {
    render(filters("color=R&color=C&type=instant"));
    expect(screen.getByRole("checkbox", { name: "Red" })).toBeChecked();
    expect(screen.getByRole("checkbox", { name: "Colorless" })).toBeChecked();
    expect(screen.getByRole("checkbox", { name: "Blue" })).not.toBeChecked();
    expect(select("Card type")).toHaveValue("instant");
  });

  it("applies a type at once, keeping the run, name, order, view and page size", async () => {
    const user = userEvent.setup();
    render(
      filters("q=bolt&sort=win_rate&order=asc&view=risers&limit=50&offset=24"),
    );
    await user.selectOptions(select("Card type"), "instant");
    expect(replaced()).toEqual([
      ["format", "Modern"],
      ["score_run_id", "run-1"],
      ["q", "bolt"],
      ["sort", "win_rate"],
      ["order", "asc"],
      ["view", "risers"],
      ["limit", "50"],
      ["type", "instant"],
    ]);
  });

  it("applies a color at once and leaves unset filters out", async () => {
    const user = userEvent.setup();
    render(filters());
    await user.click(screen.getByRole("checkbox", { name: "Green" }));
    expect(replaced()).toEqual([
      ["format", "Modern"],
      ["score_run_id", "run-1"],
      ["color", "G"],
    ]);
  });

  it("applies the form on submit instead of reloading the page", () => {
    render(filters("sort=decks"));
    const form = screen.getByRole("form", { name: "Ranking filters" });
    expect(fireEvent.submit(form)).toBe(false);
    expect(replaced()).toEqual([
      ["format", "Modern"],
      ["score_run_id", "run-1"],
      ["sort", "decks"],
    ]);
  });

  it("offers each published window and applies the chosen one", async () => {
    const user = userEvent.setup();
    render(
      <RankingFilters
        format="Modern"
        scoreRunId="run-1"
        query=""
        clearHref={clearHref}
        views={views}
        windows={[
          { scoreRunId: "run-1", label: "Since Jan 1, 2024" },
          { scoreRunId: "run-0", label: "Mar 1 – Aug 31, 2026" },
        ]}
      />,
    );
    expect(select("Window")).toHaveValue("run-1");
    await user.selectOptions(select("Window"), "run-0");
    expect(replaced()).toEqual([
      ["format", "Modern"],
      ["score_run_id", "run-0"],
    ]);
  });

  it("shows sources only when there are several", () => {
    const sources = [
      {
        source: "topdeck",
        label: "TopDeck",
        href: "/rankings?td",
        current: true,
      },
      { source: "mtgo", label: "mtgo", href: "/rankings?mtgo", current: false },
    ];
    const { rerender } = render(
      <RankingFilters
        format="Modern"
        scoreRunId="run-1"
        query=""
        clearHref={clearHref}
        views={views}
        sources={sources}
      />,
    );
    const nav = within(screen.getByRole("navigation", { name: "Sources" }));
    expect(nav.getByRole("link", { name: "TopDeck" })).toHaveAttribute(
      "aria-current",
      "page",
    );
    expect(nav.getByRole("link", { name: "mtgo" })).toHaveAttribute(
      "href",
      "/rankings?mtgo",
    );
    rerender(
      <RankingFilters
        format="Modern"
        scoreRunId="run-1"
        query=""
        clearHref={clearHref}
        views={views}
        sources={sources.slice(0, 1)}
      />,
    );
    expect(screen.queryByRole("navigation", { name: "Sources" })).toBeNull();
  });

  it.each([["q=bolt"], ["type=land"], ["color=W"]])(
    "offers to clear %s",
    (query) => {
      render(filters(query));
      expect(
        screen.getByRole("link", { name: "Clear filters" }),
      ).toHaveAttribute("href", clearHref);
    },
  );

  it("follows the address when a link elsewhere changes the filters", () => {
    const { rerender } = render(filters("color=R&type=instant"));
    rerender(filters("color=U"));
    expect(screen.getByRole("checkbox", { name: "Red" })).not.toBeChecked();
    expect(screen.getByRole("checkbox", { name: "Blue" })).toBeChecked();
    expect(select("Card type")).toHaveValue("");
    expect(router.replace).not.toHaveBeenCalled();
  });
});
