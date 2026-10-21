import { fireEvent, render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import type { ComponentProps } from "react";
import { describe, expect, it } from "vitest";
import { router } from "@/test/navigation";
import { RankingFilters, type SortOption } from "./ranking-filters";

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

  it("applies a type at once, keeping the run, search, order, view and page size", async () => {
    const user = userEvent.setup();
    render(
      filters(
        "q=bolt&in=text&sort=win_rate&order=asc&view=risers&limit=50&offset=24",
      ),
    );
    await user.selectOptions(select("Card type"), "instant");
    expect(replaced()).toEqual([
      ["format", "Modern"],
      ["score_run_id", "run-1"],
      ["q", "bolt"],
      ["in", "text"],
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

  const gradings = [
    { value: "", label: "Constructed score", disabled: false },
    { value: "signature-score", label: "Signature score", disabled: false },
    { value: "max-ratio", label: "Relative volume", disabled: false },
  ];

  function graded(query: string, method = "", options = gradings) {
    return (
      <RankingFilters
        format="Modern"
        scoreRunId="run-1"
        query={query}
        clearHref={clearHref}
        views={views}
        gradings={options}
        method={method}
      />
    );
  }

  it("offers each grading and applies the chosen one, keeping order and view", async () => {
    const user = userEvent.setup();
    render(graded("sort=win_rate&view=risers"));
    expect(
      within(select("Grading"))
        .getAllByRole("option")
        .map((option) => option.textContent),
    ).toEqual(["Constructed score", "Signature score", "Relative volume"]);
    expect(select("Grading")).toHaveValue("");
    await user.selectOptions(select("Grading"), "signature-score");
    expect(replaced()).toEqual([
      ["format", "Modern"],
      ["score_run_id", "run-1"],
      ["sort", "win_rate"],
      ["view", "risers"],
      ["method", "signature-score"],
    ]);
  });

  it("leaves the default grading out of the address", async () => {
    const user = userEvent.setup();
    render(graded("", "signature-score"));
    expect(select("Grading")).toHaveValue("signature-score");
    await user.selectOptions(select("Grading"), "");
    expect(replaced()).toEqual([
      ["format", "Modern"],
      ["score_run_id", "run-1"],
    ]);
  });

  it("disables a grading that could not score the run", () => {
    render(
      graded("", "", [
        gradings[0],
        {
          value: "signature-score",
          label: "Signature score · needs archetype labels",
          disabled: true,
        },
      ]),
    );
    expect(
      screen.getByRole("option", { name: /needs archetype labels/ }),
    ).toBeDisabled();
  });

  it("keeps a chosen grading when there is nothing to choose between", async () => {
    const user = userEvent.setup();
    render(graded("", "signature-score", []));
    expect(screen.queryByRole("combobox", { name: "Grading" })).toBeNull();
    await user.selectOptions(select("Card type"), "land");
    expect(replaced()).toEqual([
      ["format", "Modern"],
      ["score_run_id", "run-1"],
      ["method", "signature-score"],
      ["type", "land"],
    ]);
  });

  it("follows the address when a link elsewhere changes the grading", () => {
    const { rerender } = render(graded("", "signature-score"));
    rerender(graded("", "max-ratio"));
    expect(select("Grading")).toHaveValue("max-ratio");
    expect(router.replace).not.toHaveBeenCalled();
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

describe("RankingFilters for commanders", () => {
  const kinds = [
    { label: "Cards", href: "/rankings?format=EDH", current: false },
    {
      label: "Commanders",
      href: "/rankings/commanders?format=EDH",
      current: true,
    },
  ];

  function commanders(query = "") {
    return (
      <RankingFilters
        format="EDH"
        scoreRunId="run-1"
        query={query}
        clearHref="/rankings/commanders?format=EDH&score_run_id=run-1"
        kinds={kinds}
        action="/rankings/commanders"
        types={false}
        minDecks={[
          { value: "", label: "Any number of decks" },
          { value: "10", label: "10+ decks" },
          { value: "50", label: "50+ decks" },
        ]}
        label="Commander filters"
        updating="Updating commanders…"
      />
    );
  }

  it("switches between cards and commanders, without views or card types", () => {
    render(commanders());
    const form = screen.getByRole("form", { name: "Commander filters" });
    expect(form).toHaveAttribute("action", "/rankings/commanders");
    const switcher = within(screen.getByRole("navigation", { name: "Rank" }));
    expect(switcher.getByRole("link", { name: "Commanders" })).toHaveAttribute(
      "aria-current",
      "page",
    );
    expect(switcher.getByRole("link", { name: "Cards" })).toHaveAttribute(
      "href",
      "/rankings?format=EDH",
    );
    expect(screen.queryByRole("navigation", { name: "Views" })).toBeNull();
    expect(screen.queryByRole("combobox", { name: "Card type" })).toBeNull();
  });

  it("applies a color on the commanders page", async () => {
    const user = userEvent.setup();
    render(commanders("sort=win_rate"));
    await user.click(screen.getByRole("checkbox", { name: "Green" }));
    expect(router.replace).toHaveBeenCalledTimes(1);
    const url = new URL(
      String(router.replace.mock.calls[0][0]),
      location.origin,
    );
    expect(url.pathname).toBe("/rankings/commanders");
    expect([...url.searchParams]).toEqual([
      ["format", "EDH"],
      ["score_run_id", "run-1"],
      ["sort", "win_rate"],
      ["color", "G"],
    ]);
  });

  it("applies a minimum of decks and offers to clear it", async () => {
    const user = userEvent.setup();
    render(commanders("min_decks=10"));
    expect(select("Minimum decks")).toHaveValue("10");
    expect(
      screen.getByRole("link", { name: "Clear filters" }),
    ).toBeInTheDocument();
    await user.selectOptions(select("Minimum decks"), "50");
    const url = new URL(
      String(router.replace.mock.calls[0][0]),
      location.origin,
    );
    expect([...url.searchParams]).toEqual([
      ["format", "EDH"],
      ["score_run_id", "run-1"],
      ["min_decks", "50"],
    ]);
  });

  it("follows the address when a link elsewhere changes the minimum of decks", () => {
    const { rerender } = render(commanders("min_decks=10"));
    rerender(commanders("min_decks=50"));
    expect(select("Minimum decks")).toHaveValue("50");
    expect(router.replace).not.toHaveBeenCalled();
  });

  it("shows no switch where a format has no commanders", () => {
    render(filters());
    expect(screen.queryByRole("navigation", { name: "Rank" })).toBeNull();
    expect(
      screen.queryByRole("combobox", { name: "Minimum decks" }),
    ).toBeNull();
  });
});

describe("RankingFilters menu", () => {
  const sorts: SortOption[] = [
    { value: "", label: "Grade", order: "desc" },
    { value: "name", label: "Card", order: "asc" },
    { value: "win_rate", label: "Win rate vs field", order: "desc" },
  ];

  function menu(
    query = "",
    props: Partial<ComponentProps<typeof RankingFilters>> = {},
  ) {
    // The page marks the view the address names, as the API returned it.
    const view = new URLSearchParams(query).get("view") ?? "all";
    return (
      <RankingFilters
        format="Modern"
        scoreRunId="run-1"
        query={query}
        clearHref={clearHref}
        views={views.map((tab) => ({ ...tab, current: tab.view === view }))}
        sorts={sorts}
        {...props}
      />
    );
  }

  /** The button that opens and closes the menu. */
  function toggle() {
    return screen.getByRole("button", { name: /^Filters/ });
  }

  /** Opens the menu from the toolbar and returns queries within it. */
  async function open(user: ReturnType<typeof userEvent.setup>) {
    await user.click(toggle());
    return within(screen.getByRole("region", { name: "Filters" }));
  }

  /** Whether the menu shows; a closed one is hidden from every role query. */
  function shown() {
    return screen.queryByRole("region", { name: "Filters" }) !== null;
  }

  it("offers no menu without sorts", () => {
    render(filters());
    expect(screen.queryByRole("button", { name: /^Filters/ })).toBeNull();
  });

  it("counts each kind of filter set on its button", () => {
    render(menu("q=bolt&type=land&color=R&color=G&view=risers&sort=name"));
    const button = screen.getByRole("button", {
      name: "Filters 4 active filters",
    });
    expect(button).toHaveAttribute("aria-expanded", "false");
    expect(button.querySelector(".filter-menu-count")).toHaveTextContent("4");
  });

  it("opens on the address, with every filter and order", async () => {
    const user = userEvent.setup();
    render(
      menu(
        "q=bolt&color=R&type=instant&view=risers&sort=win_rate&order=asc&limit=50",
      ),
    );
    expect(shown()).toBe(false);
    const dialog = await open(user);
    // It opens in the toolbar, under its controls, and the button names it.
    const panel = screen.getByRole("region", { name: "Filters" });
    expect(toggle()).toHaveAttribute("aria-expanded", "true");
    expect(toggle()).toHaveAttribute("aria-controls", panel.id);
    expect(panel.closest(".ranking-toolbar")).not.toBeNull();
    expect(dialog.getByRole("heading", { name: "Filters" })).toBeVisible();
    expect(
      dialog.getByRole("searchbox", { name: "Search ranked cards" }),
    ).toHaveValue("bolt");
    expect(dialog.getByRole("radio", { name: /Risers/ })).toBeChecked();
    expect(dialog.getByRole("radio", { name: /All/ })).not.toBeChecked();
    expect(dialog.getByRole("checkbox", { name: "Red" })).toBeChecked();
    expect(dialog.getByRole("checkbox", { name: "Blue" })).not.toBeChecked();
    expect(dialog.getByRole("combobox", { name: "Card type" })).toHaveValue(
      "instant",
    );
    const sort = dialog.getByRole("combobox", { name: "Sort by" });
    expect(
      within(sort)
        .getAllByRole("option")
        .map((o) => o.textContent),
    ).toEqual(["Grade", "Card", "Win rate vs field"]);
    expect(sort).toHaveValue("win_rate");
    expect(dialog.getByRole("radio", { name: "Ascending" })).toBeChecked();
    const limit = dialog.getByRole("combobox", { name: "Cards per page" });
    expect(
      within(limit)
        .getAllByRole("option")
        .map((o) => o.textContent),
    ).toEqual(["25", "50", "75", "100"]);
    expect(limit).toHaveValue("50");
    // The toolbar's other controls are not repeated where there is one choice.
    expect(dialog.queryByRole("combobox", { name: "Grading" })).toBeNull();
    expect(dialog.queryByRole("combobox", { name: "Window" })).toBeNull();
    expect(
      dialog.queryByRole("combobox", { name: "Minimum decks" }),
    ).toBeNull();
  });

  it("applies every change at once, dropping the page offset and the order a sort starts in", async () => {
    const user = userEvent.setup();
    render(
      menu(
        "q=bolt&color=R&view=risers&sort=win_rate&order=asc&limit=50&offset=24",
      ),
    );
    const dialog = await open(user);
    const search = dialog.getByRole("searchbox", {
      name: "Search ranked cards",
    });
    await user.clear(search);
    await user.type(search, "fire");
    await user.click(dialog.getByRole("checkbox", { name: "Red" }));
    await user.click(dialog.getByRole("checkbox", { name: "Green" }));
    await user.selectOptions(
      dialog.getByRole("combobox", { name: "Card type" }),
      "instant",
    );
    // Names start ascending, so the kept order needs no place in the address.
    await user.selectOptions(
      dialog.getByRole("combobox", { name: "Sort by" }),
      "name",
    );
    expect(router.replace).not.toHaveBeenCalled();
    await user.click(dialog.getByRole("button", { name: "Show results" }));
    expect(replaced()).toEqual([
      ["format", "Modern"],
      ["score_run_id", "run-1"],
      ["q", "fire"],
      ["view", "risers"],
      ["color", "G"],
      ["type", "instant"],
      ["sort", "name"],
      ["limit", "50"],
    ]);
    expect(shown()).toBe(false);
    expect(toggle()).toHaveFocus();
  });

  it("keeps an order the sort does not start in, and a grading with no menu", async () => {
    const user = userEvent.setup();
    render(menu("view=risers&limit=100", { method: "max-ratio" }));
    const dialog = await open(user);
    expect(dialog.getByRole("radio", { name: "Descending" })).toBeChecked();
    await user.click(dialog.getByRole("radio", { name: /All/ }));
    await user.click(dialog.getByRole("radio", { name: "Ascending" }));
    await user.selectOptions(
      dialog.getByRole("combobox", { name: "Cards per page" }),
      "25",
    );
    await user.click(dialog.getByRole("button", { name: "Show results" }));
    expect(replaced()).toEqual([
      ["format", "Modern"],
      ["score_run_id", "run-1"],
      ["method", "max-ratio"],
      ["order", "asc"],
    ]);
  });

  it("chooses the grading, window and minimum of decks where there are several", async () => {
    const user = userEvent.setup();
    render(
      menu("", {
        views: [],
        types: false,
        gradings: [
          { value: "", label: "Constructed score", disabled: false },
          { value: "max-ratio", label: "Relative volume", disabled: false },
        ],
        method: "max-ratio",
        windows: [
          { scoreRunId: "run-1", label: "Since Jan 1, 2024" },
          { scoreRunId: "run-0", label: "Mar 1 – Aug 31, 2026" },
        ],
        minDecks: [
          { value: "", label: "Any number of decks" },
          { value: "10", label: "10+ decks" },
        ],
      }),
    );
    const dialog = await open(user);
    expect(dialog.queryByRole("radiogroup", { name: "Views" })).toBeNull();
    expect(dialog.queryByRole("combobox", { name: "Card type" })).toBeNull();
    expect(dialog.getByRole("combobox", { name: "Grading" })).toHaveValue(
      "max-ratio",
    );
    await user.selectOptions(
      dialog.getByRole("combobox", { name: "Window" }),
      "run-0",
    );
    await user.selectOptions(
      dialog.getByRole("combobox", { name: "Minimum decks" }),
      "10",
    );
    await user.click(dialog.getByRole("button", { name: "Show results" }));
    expect(replaced()).toEqual([
      ["format", "Modern"],
      ["method", "max-ratio"],
      ["score_run_id", "run-0"],
      ["min_decks", "10"],
    ]);
  });

  it("drops changes it closes without applying", async () => {
    const user = userEvent.setup();
    render(menu("q=bolt"));
    let dialog = await open(user);
    await user.type(
      dialog.getByRole("searchbox", { name: "Search ranked cards" }),
      "xyz",
    );
    await user.click(dialog.getByRole("button", { name: "Dismiss" }));
    expect(shown()).toBe(false);
    expect(toggle()).toHaveFocus();
    dialog = await open(user);
    expect(
      dialog.getByRole("searchbox", { name: "Search ranked cards" }),
    ).toHaveValue("bolt");
    expect(router.replace).not.toHaveBeenCalled();
  });

  it("closes on its button and on Escape, which returns focus to the button", async () => {
    const user = userEvent.setup();
    render(menu());
    await open(user);
    await user.click(toggle());
    expect(shown()).toBe(false);
    expect(toggle()).toHaveAttribute("aria-expanded", "false");
    // Other keys, and Escape while it is closed, leave it as it is.
    await user.keyboard("{Escape}");
    expect(shown()).toBe(false);
    const dialog = await open(user);
    dialog.getByRole("combobox", { name: "Sort by" }).focus();
    await user.keyboard("{ArrowDown}");
    expect(shown()).toBe(true);
    await user.keyboard("{Escape}");
    expect(shown()).toBe(false);
    expect(toggle()).toHaveFocus();
  });

  it("clears every filter from the menu and closes it", async () => {
    const user = userEvent.setup();
    render(menu("type=land"));
    const dialog = await open(user);
    const clear = dialog.getByRole("link", { name: "Clear filters" });
    expect(clear).toHaveAttribute("href", clearHref);
    // Stops the link's navigation, which jsdom does not implement.
    clear.addEventListener("click", (event) => event.preventDefault());
    await user.click(clear);
    expect(shown()).toBe(false);
  });

  it("searches the part of each card it names, the whole card by default", async () => {
    const user = userEvent.setup();
    render(menu("q=elf&in=text"));
    const dialog = await open(user);
    const field = dialog.getByRole("combobox", { name: "Search in" });
    expect(
      within(field)
        .getAllByRole("option")
        .map((o) => o.textContent),
    ).toEqual(["Whole card", "Name", "Type line", "Rules text"]);
    expect(field).toHaveValue("text");
    await user.selectOptions(field, "type");
    await user.click(dialog.getByRole("button", { name: "Show results" }));
    expect(replaced()).toEqual([
      ["format", "Modern"],
      ["score_run_id", "run-1"],
      ["in", "type"],
      ["q", "elf"],
    ]);
  });

  it("leaves where to search out without text to search for", async () => {
    const user = userEvent.setup();
    render(menu("q=elf&in=type"));
    const dialog = await open(user);
    await user.clear(
      dialog.getByRole("searchbox", { name: "Search ranked cards" }),
    );
    await user.click(dialog.getByRole("button", { name: "Show results" }));
    expect(replaced()).toEqual([
      ["format", "Modern"],
      ["score_run_id", "run-1"],
    ]);
  });

  it("names the search and page size the commanders page passes, and applies there", async () => {
    const user = userEvent.setup();
    render(
      <RankingFilters
        format="EDH"
        scoreRunId="run-1"
        query="min_decks=10&sort=win_rate"
        clearHref="/rankings/commanders?format=EDH&score_run_id=run-1"
        action="/rankings/commanders"
        types={false}
        minDecks={[
          { value: "", label: "Any number of decks" },
          { value: "10", label: "10+ decks" },
          { value: "50", label: "50+ decks" },
        ]}
        sorts={[
          { value: "", label: "Meta share", order: "desc" },
          { value: "name", label: "Commander", order: "asc" },
          { value: "win_rate", label: "Win rate vs field", order: "desc" },
        ]}
        fields={false}
        search="Search commanders"
        perPage="Commanders per page"
        label="Commander filters"
      />,
    );
    expect(
      screen.getByRole("button", { name: "Filters 1 active filter" }),
    ).toBeInTheDocument();
    const dialog = await open(user);
    expect(
      dialog.getByRole("searchbox", { name: "Search commanders" }),
    ).toBeInTheDocument();
    // Commanders are searched by name only.
    expect(dialog.queryByRole("combobox", { name: "Search in" })).toBeNull();
    expect(dialog.getByRole("combobox", { name: "Minimum decks" })).toHaveValue(
      "10",
    );
    expect(dialog.queryByRole("combobox", { name: "Card type" })).toBeNull();
    await user.selectOptions(
      dialog.getByRole("combobox", { name: "Sort by" }),
      "",
    );
    await user.selectOptions(
      dialog.getByRole("combobox", { name: "Commanders per page" }),
      "50",
    );
    await user.click(dialog.getByRole("button", { name: "Show results" }));
    const url = new URL(
      String(router.replace.mock.calls[0][0]),
      location.origin,
    );
    expect(url.pathname).toBe("/rankings/commanders");
    expect([...url.searchParams]).toEqual([
      ["format", "EDH"],
      ["score_run_id", "run-1"],
      ["min_decks", "10"],
      ["limit", "50"],
    ]);
  });
});
