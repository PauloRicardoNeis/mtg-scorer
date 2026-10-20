import { fireEvent, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";
import { router } from "@/test/navigation";
import { CompareFilters, type PickOption } from "./compare-filters";

const formats: PickOption[] = [
  { value: "Modern", label: "Modern", checked: true },
  { value: "Legacy", label: "Legacy", checked: false },
];
const stats: PickOption[] = [
  { value: "grade", label: "Grade", checked: true },
  { value: "share", label: "Meta share", checked: false },
];
const summaries: PickOption[] = [
  { value: "best", label: "Best format", checked: true },
];

function filters(
  query = "",
  every = false,
  options = { formats, stats, summaries },
) {
  return (
    <CompareFilters
      formats={options.formats}
      stats={options.stats}
      summaries={options.summaries}
      every={every}
      query={query}
    />
  );
}

/** The query of the address the filters replaced, as pairs. */
function replaced(): [string, string][] {
  expect(router.replace).toHaveBeenCalledTimes(1);
  const [href, options] = router.replace.mock.calls[0];
  expect(options).toEqual({ scroll: false });
  const url = new URL(String(href), location.origin);
  expect(url.pathname).toBe("/rankings/compare");
  return [...url.searchParams];
}

describe("CompareFilters", () => {
  it("names each group and submits as a GET form without JavaScript", () => {
    render(filters());
    const form = screen.getByRole("form", { name: "Compare settings" });
    expect(form).toHaveAttribute("action", "/rankings/compare");
    expect(form).toHaveAttribute("method", "get");
    for (const name of ["Formats", "Stats", "Summary", "Colors"])
      expect(screen.getByRole("group", { name })).toBeInTheDocument();
    expect(screen.getByRole("checkbox", { name: "Modern" })).toBeChecked();
    expect(
      screen.getByRole("switch", { name: "In every selected format" }),
    ).not.toBeChecked();
  });

  it("applies a chip at once, keeping the search, order and page size", async () => {
    const user = userEvent.setup();
    render(
      filters("q=bolt&sort=Modern:grade&order=asc&limit=100&offset=50&color=R"),
    );
    await user.click(screen.getByRole("checkbox", { name: "Legacy" }));
    expect(replaced()).toEqual([
      ["picked", "1"],
      ["q", "bolt"],
      ["sort", "Modern:grade"],
      ["order", "asc"],
      ["limit", "100"],
      ["format", "Modern"],
      ["format", "Legacy"],
      ["stat", "grade"],
      ["summary", "best"],
      ["color", "R"],
    ]);
  });

  it("keeps the last format and stat on, but lets every summary go", async () => {
    const user = userEvent.setup();
    render(filters());
    await user.click(screen.getByRole("checkbox", { name: "Modern" }));
    await user.click(screen.getByRole("checkbox", { name: "Grade" }));
    expect(screen.getByRole("checkbox", { name: "Modern" })).toBeChecked();
    expect(screen.getByRole("checkbox", { name: "Grade" })).toBeChecked();
    expect(router.replace).not.toHaveBeenCalled();
    await user.click(screen.getByRole("checkbox", { name: "Best format" }));
    expect(replaced()).toEqual([
      ["picked", "1"],
      ["format", "Modern"],
      ["stat", "grade"],
    ]);
  });

  it("turns on the every-format switch", async () => {
    const user = userEvent.setup();
    render(filters());
    await user.click(
      screen.getByRole("switch", { name: "In every selected format" }),
    );
    expect(replaced()).toContainEqual(["every", "true"]);
  });

  it("applies on submit instead of reloading the page", () => {
    render(filters("", true));
    expect(
      fireEvent.submit(screen.getByRole("form", { name: "Compare settings" })),
    ).toBe(false);
    expect(replaced()).toContainEqual(["every", "true"]);
  });

  it("follows the address when a preset or another link changes the choices", () => {
    const { rerender } = render(filters("color=R"));
    rerender(
      filters("color=U", true, {
        formats: formats.map((f) => ({ ...f, checked: f.value === "Legacy" })),
        stats: stats.map((s) => ({ ...s, checked: true })),
        summaries: summaries.map((s) => ({ ...s, checked: false })),
      }),
    );
    expect(screen.getByRole("checkbox", { name: "Modern" })).not.toBeChecked();
    expect(screen.getByRole("checkbox", { name: "Legacy" })).toBeChecked();
    expect(screen.getByRole("checkbox", { name: "Meta share" })).toBeChecked();
    expect(
      screen.getByRole("checkbox", { name: "Best format" }),
    ).not.toBeChecked();
    expect(screen.getByRole("checkbox", { name: "Blue" })).toBeChecked();
    expect(screen.getByRole("checkbox", { name: "Red" })).not.toBeChecked();
    expect(
      screen.getByRole("switch", { name: "In every selected format" }),
    ).toBeChecked();
    expect(router.replace).not.toHaveBeenCalled();
  });
});
