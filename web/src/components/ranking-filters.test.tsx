import { fireEvent, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";
import { router } from "@/test/navigation";
import { RankingFilters } from "./ranking-filters";

const clearHref = "/rankings?format=Modern&score_run_id=run-1";

function filters(query = "") {
  return (
    <RankingFilters
      format="Modern"
      scoreRunId="run-1"
      query={query}
      clearHref={clearHref}
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
    expect(
      screen.getByRole("form", { name: "Ranking filters" }),
    ).toHaveAttribute("action", "/rankings");
    // Without JavaScript the form still submits as a plain GET.
    expect(
      screen.getByRole("form", { name: "Ranking filters" }),
    ).toHaveAttribute("method", "get");
    expect(screen.getByRole("group", { name: "Colors" })).toBeInTheDocument();
    expect(screen.getByText("Colors")).toHaveClass("sr-only");
    expect(select("Card type")).toHaveValue("");
    expect(select("Sort by")).toHaveValue("score");
    expect(screen.queryByRole("link", { name: "Clear filters" })).toBeNull();
  });

  it("reflects the filters in the query", () => {
    render(filters("color=R&color=C&type=instant&sort=name"));
    expect(screen.getByRole("checkbox", { name: "Red" })).toBeChecked();
    expect(screen.getByRole("checkbox", { name: "Colorless" })).toBeChecked();
    expect(screen.getByRole("checkbox", { name: "Blue" })).not.toBeChecked();
    expect(select("Card type")).toHaveValue("instant");
    expect(select("Sort by")).toHaveValue("name");
  });

  it("applies a type at once, keeping the run, the name and the page size", async () => {
    const user = userEvent.setup();
    render(filters("q=bolt&limit=50&offset=24"));
    await user.selectOptions(select("Card type"), "instant");
    expect(replaced()).toEqual([
      ["format", "Modern"],
      ["score_run_id", "run-1"],
      ["q", "bolt"],
      ["limit", "50"],
      ["type", "instant"],
      ["sort", "score"],
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
      ["sort", "score"],
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
    const { rerender } = render(filters("color=R&type=instant&sort=name"));
    rerender(filters("color=U"));
    expect(screen.getByRole("checkbox", { name: "Red" })).not.toBeChecked();
    expect(screen.getByRole("checkbox", { name: "Blue" })).toBeChecked();
    expect(select("Card type")).toHaveValue("");
    expect(select("Sort by")).toHaveValue("score");
    expect(router.replace).not.toHaveBeenCalled();
  });
});
