import { fireEvent, render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import type { Printing, RankedCard } from "@/lib/api";
import { router } from "@/test/navigation";
import { RankingTable } from "./ranking-table";

const method = {
  method_id: "max-ratio",
  method_version: "max-ratio-v1",
  label: "Relative volume",
  description: "Decks with the card, against the most-played card.",
  outputs: ["max_ratio"],
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
    archetype_deck_count: 3,
    archetype_label: "Burn",
    color_identity: ["R"],
    deck_count: 4,
    event_count: 2,
    labelled_deck_count: 4,
    mana_cost: "{R}",
    name: "Lightning Bolt",
    oracle_id: "bolt",
    preview_printing: printing([
      { face_index: null, artist: null, source_uri: "https://img/bolt.jpg" },
    ]),
    rank: 1,
    score: 100,
    top_cut_count: 3,
    top_cut_known_decks: 4,
    type_line: "Instant",
    ...overrides,
  };
}

const bolt = card({});
const fire = card({
  oracle_id: "fire",
  name: "Fire // Ice",
  rank: 2,
  score: 50,
  deck_count: 2,
  event_count: 1,
  mana_cost: "{1}{R} // {1}{U}",
  type_line: "Instant // Instant",
  archetype_label: null,
  archetype_deck_count: 0,
  labelled_deck_count: 0,
  top_cut_count: null,
  top_cut_known_decks: 0,
  preview_printing: printing([]),
});
const unlisted = card({
  oracle_id: "unlisted",
  name: "Synthetic Unlisted Card",
  rank: 3,
  score: null,
  deck_count: 1,
  mana_cost: null,
  type_line: null,
  preview_printing: null,
});

function table(items: RankedCard[], catalog: string | null = "snap-1") {
  return (
    <RankingTable
      items={items}
      decks={7}
      method={method}
      catalogSnapshotId={catalog}
      clearHref="/rankings?format=Modern"
      footer={<p role="status">1–3 of 3 ranked cards</p>}
    />
  );
}

function row(name: RegExp): HTMLElement {
  return screen.getByRole("row", { name });
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
      expect.stringContaining("Relative volume"),
      "Meta share",
      "Events",
      "Top cuts",
      "Most played in",
    ]);
    await user.hover(screen.getByRole("button", { name: "About this score" }));
    const tooltip = screen.getByRole("tooltip");
    expect(tooltip).toHaveTextContent("Method");
    expect(tooltip).toHaveTextContent(method.description);
    expect(tooltip).toHaveTextContent("max-ratio-v1");
  });

  it("shows each card's rank, numbers and archetype", () => {
    render(table([bolt, fire, unlisted]));
    const cells = within(row(/Lightning Bolt/)).getAllByRole("cell");
    expect(cells.map((cell) => cell.textContent)).toEqual([
      "1",
      "100.0",
      "57.1%",
      "2",
      "3of 4 known",
      "Burn3 of 4 decks",
    ]);
    expect(
      within(row(/Lightning Bolt/))
        .getByRole("rowheader")
        .querySelector(".thumb img"),
    ).toHaveAttribute("src", "https://img/bolt.jpg");
    expect(within(row(/Lightning Bolt/)).getByText("{R}")).toHaveClass(
      "sr-only",
    );
    expect(within(row(/Fire/)).getAllByRole("cell")[4]).toHaveTextContent(
      "Unknown",
    );
    expect(within(row(/Fire/)).getAllByRole("cell")[5]).toHaveTextContent(
      "Unlabelled",
    );
    expect(within(row(/Unlisted/)).getAllByRole("cell")[1]).toHaveTextContent(
      "Unknown",
    );
    expect(row(/Unlisted/)).toHaveTextContent("Not in this catalog");
  });

  it("sizes share bars against the largest share on the page", () => {
    const { container } = render(table([bolt, fire]));
    const bars = [...container.querySelectorAll<HTMLElement>(".share-bar")];
    expect(bars.map((bar) => bar.style.getPropertyValue("--fill"))).toEqual([
      "100%",
      "50%",
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
    expect(
      preview().getByRole("img", {
        name: "Lightning Bolt — Magic 2011 #149 (EN)",
      }),
    ).toHaveAttribute("src", "https://img/bolt.jpg");
    expect(preview().getByText("100.0")).toBeInTheDocument();
    expect(preview().getByText("57.1%")).toBeInTheDocument();
    expect(preview().getByText("Burn")).toBeInTheDocument();
    expect(preview().getByText("75.0%")).toBeInTheDocument();
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
    expect(preview().getByText("Unknown")).toBeInTheDocument();
    expect(preview().getByText("No labelled decks")).toBeInTheDocument();

    fireEvent.focus(row(/Unlisted/));
    expect(preview().getByText("Rank 3")).toBeInTheDocument();
    expect(preview().getByText("Synthetic Unlisted Card")).toHaveClass(
      "preview-placeholder",
    );
    expect(preview().getByText("—")).toBeInTheDocument();
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
    await user.click(within(row(/Lightning Bolt/)).getAllByRole("cell")[2]);
    expect(router.push).toHaveBeenCalledExactlyOnceWith(
      "/cards/bolt?catalog_snapshot_id=snap-1",
    );
  });

  it("leaves the name link, text selection and unlisted cards alone", async () => {
    const user = userEvent.setup();
    render(table([bolt, unlisted], "snap-1"));
    const link = within(row(/Lightning Bolt/)).getByRole("link");
    link.addEventListener("click", (event) => event.preventDefault());
    await user.click(link);
    await user.click(row(/Unlisted/));
    vi.spyOn(window, "getSelection").mockReturnValue({
      toString: () => "Lightning",
    } as Selection);
    await user.click(within(row(/Lightning Bolt/)).getAllByRole("cell")[0]);
    expect(router.push).not.toHaveBeenCalled();
  });

  it("opens nothing without a joined catalog", async () => {
    const user = userEvent.setup();
    render(table([bolt], null));
    expect(within(row(/Lightning Bolt/)).queryByRole("link")).toBeNull();
    await user.click(row(/Lightning Bolt/));
    expect(router.push).not.toHaveBeenCalled();
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
