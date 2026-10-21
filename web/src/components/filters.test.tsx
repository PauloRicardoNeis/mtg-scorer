import { act, render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";
import type { Snapshot } from "@/lib/api";
import { router } from "@/test/navigation";
import { Filters } from "./filters";

const snapshot: Snapshot = {
  attribution: [],
  card_count: 3,
  catalog_snapshot_id: "snap-1",
  created_at: "2026-10-01T00:00:00Z",
  excluded_record_counts: {},
  parser_version: "1",
  printing_count: 4,
  published_at: "2026-10-01T00:00:00Z",
  retrieved_from: "2026-09-30T00:00:00Z",
  retrieved_to: "2026-09-30T00:00:00Z",
  schema_version: "1",
  selection: { kind: "sets", description: "Two core sets" },
  sets: [
    { set_code: "m11", set_name: "Magic 2011" },
    { set_code: "lea", set_name: "Limited Edition Alpha" },
  ],
  source: "scryfall",
  tournament_evidence: { state: "none", reason_codes: [] },
};

function select(label: string): HTMLSelectElement {
  return screen.getByLabelText<HTMLSelectElement>(label);
}

function optionLabels(element: HTMLSelectElement): string[] {
  return [...element.options].map((option) => option.textContent ?? "");
}

function selectedValues(element: HTMLSelectElement): string[] {
  return [...element.selectedOptions].map((option) => option.value);
}

describe("Filters", () => {
  describe("initial state", () => {
    it("starts empty with 24 cards per page", () => {
      render(<Filters snapshot={snapshot} query="" />);
      expect(
        screen.getByRole("searchbox", { name: "Name, type or text" }),
      ).toHaveValue("");
      for (const box of screen.getAllByRole("checkbox"))
        expect(box).not.toBeChecked();
      expect(select("Card type")).toHaveValue("");
      expect(selectedValues(select("Sets"))).toEqual([]);
      expect(selectedValues(select("Rarity"))).toEqual([]);
      expect(select("Color identity")).toHaveValue("");
      expect(select("Game")).toHaveValue("");
      expect(select("Cards per page")).toHaveValue("24");
      expect(select("Search in")).toHaveValue("");
    });

    it("reflects every filter in the query", () => {
      render(
        <Filters
          snapshot={snapshot}
          query="q=Bolt&in=name&color=R&color=C&type=instant&set=m11&set=lea&rarity=rare&rarity=mythic&color_identity=WU&game=arena&limit=50"
        />,
      );
      expect(
        screen.getByRole("searchbox", { name: "Name, type or text" }),
      ).toHaveValue("Bolt");
      expect(select("Search in")).toHaveValue("name");
      expect(screen.getByRole("checkbox", { name: "Red" })).toBeChecked();
      expect(screen.getByRole("checkbox", { name: "Colorless" })).toBeChecked();
      expect(screen.getByRole("checkbox", { name: "Blue" })).not.toBeChecked();
      expect(select("Card type")).toHaveValue("instant");
      expect(selectedValues(select("Sets"))).toEqual(["m11", "lea"]);
      expect(selectedValues(select("Rarity"))).toEqual(["rare", "mythic"]);
      expect(select("Color identity")).toHaveValue("WU");
      expect(select("Game")).toHaveValue("arena");
      expect(select("Cards per page")).toHaveValue("50");
    });

    it("explains the multi-select set list", () => {
      render(<Filters snapshot={snapshot} query="" />);
      expect(select("Sets")).toHaveAccessibleDescription(
        "No selection includes all sets. Ctrl / Cmd selects several.",
      );
    });
  });

  describe("options", () => {
    it("offers every card type", () => {
      render(<Filters snapshot={snapshot} query="" />);
      expect(optionLabels(select("Card type"))).toEqual([
        "All card types",
        "Creatures",
        "Planeswalkers",
        "Instants",
        "Sorceries",
        "Artifacts",
        "Enchantments",
        "Lands",
      ]);
    });

    it("names the dataset's sets with their codes", () => {
      render(<Filters snapshot={snapshot} query="" />);
      expect(optionLabels(select("Sets"))).toEqual([
        "Magic 2011 (M11)",
        "Limited Edition Alpha (LEA)",
      ]);
    });

    it("keeps requested sets missing from the dataset, flagged and selected", () => {
      render(<Filters snapshot={snapshot} query="set=zen&set=m11" />);
      const sets = select("Sets");
      expect(optionLabels(sets)).toEqual([
        "ZEN (not in this dataset)",
        "Magic 2011 (M11)",
        "Limited Edition Alpha (LEA)",
      ]);
      expect(selectedValues(sets)).toEqual(["zen", "m11"]);
    });

    it("offers every color identity combination in WUBRG order", () => {
      render(<Filters snapshot={snapshot} query="" />);
      const labels = optionLabels(select("Color identity"));
      expect(labels).toHaveLength(2 + 31);
      expect(labels.slice(0, 6)).toEqual([
        "All, including unknown",
        "Colorless only",
        "White",
        "Blue",
        "White · Blue",
        "Black",
      ]);
      expect(labels.at(-1)).toBe("White · Blue · Black · Red · Green");
      expect(new Set(labels).size).toBe(labels.length);
    });

    it("keeps a requested identity written in another order", () => {
      render(<Filters snapshot={snapshot} query="color_identity=UW" />);
      const identity = select("Color identity");
      expect(optionLabels(identity)).toHaveLength(2 + 31 + 1);
      expect(identity).toHaveValue("UW");
      expect(identity.selectedOptions[0]).toHaveTextContent("Blue · White");
    });

    it("selects colorless without adding an option", () => {
      render(<Filters snapshot={snapshot} query="color_identity=C" />);
      const identity = select("Color identity");
      expect(optionLabels(identity)).toHaveLength(2 + 31);
      expect(identity.selectedOptions[0]).toHaveTextContent("Colorless only");
    });

    it("offers the standard page sizes", () => {
      render(<Filters snapshot={snapshot} query="" />);
      expect(optionLabels(select("Cards per page"))).toEqual([
        "2",
        "24",
        "50",
        "100",
      ]);
    });

    it("adds a requested page size in order", () => {
      render(<Filters snapshot={snapshot} query="limit=10" />);
      expect(optionLabels(select("Cards per page"))).toEqual([
        "2",
        "10",
        "24",
        "50",
        "100",
      ]);
      expect(select("Cards per page")).toHaveValue("10");
    });

    it.each(["abc", "", "0", "101", "10.5"])(
      "shows the default page size for limit=%s",
      (limit) => {
        render(<Filters snapshot={snapshot} query={`limit=${limit}`} />);
        expect(optionLabels(select("Cards per page"))).toEqual([
          "2",
          "24",
          "50",
          "100",
        ]);
        expect(select("Cards per page")).toHaveValue("24");
      },
    );

    it("offers the rarities and games", () => {
      render(<Filters snapshot={snapshot} query="" />);
      expect(optionLabels(select("Rarity"))).toEqual([
        "common",
        "uncommon",
        "rare",
        "mythic",
        "special",
        "bonus",
      ]);
      expect(optionLabels(select("Game"))).toEqual([
        "Any game",
        "Paper",
        "Magic Online",
        "Arena",
      ]);
    });

    it("clears back to the dataset's unfiltered pool", () => {
      render(<Filters snapshot={snapshot} query="q=bolt&set=m11" />);
      expect(
        screen.getByRole("link", { name: "Clear filters" }),
      ).toHaveAttribute("href", "/cards?catalog_snapshot_id=snap-1");
    });
  });

  describe("searching", () => {
    it("navigates to the chosen filters, skipping blank ones", async () => {
      const user = userEvent.setup();
      render(<Filters snapshot={snapshot} query="" />);
      const form = screen.getByRole("form", { name: "Pool filters" });
      expect(form).toHaveAttribute("action", "/cards");

      await user.type(
        screen.getByRole("searchbox", { name: "Name, type or text" }),
        "Æther & co",
      );
      await user.click(screen.getByRole("checkbox", { name: "Blue" }));
      await user.click(screen.getByRole("checkbox", { name: "Black" }));
      await user.selectOptions(select("Card type"), "Creatures");
      await user.selectOptions(select("Sets"), ["Magic 2011 (M11)"]);
      await user.selectOptions(select("Game"), "Paper");
      await user.click(screen.getByRole("button", { name: "Find cards" }));

      expect(router.push).toHaveBeenCalledTimes(1);
      expect(router.push).toHaveBeenCalledWith(
        "/cards?q=%C3%86ther+%26+co&color=U&color=B&type=creature&catalog_snapshot_id=snap-1&set=m11&game=paper&limit=24",
      );
    });

    it("keeps the dataset and page size for an empty search", async () => {
      const user = userEvent.setup();
      render(<Filters snapshot={snapshot} query="limit=50" />);
      await user.click(screen.getByRole("button", { name: "Find cards" }));
      expect(router.push).toHaveBeenCalledWith(
        "/cards?catalog_snapshot_id=snap-1&limit=50",
      );
    });

    it("submits the default page size in place of an unusable limit", async () => {
      const user = userEvent.setup();
      render(<Filters snapshot={snapshot} query="limit=abc" />);
      await user.click(screen.getByRole("button", { name: "Find cards" }));
      expect(router.push).toHaveBeenCalledWith(
        "/cards?catalog_snapshot_id=snap-1&limit=24",
      );
    });

    it("searches the part of each card chosen, only with text to search for", async () => {
      const user = userEvent.setup();
      render(<Filters snapshot={snapshot} query="" />);
      await user.selectOptions(select("Search in"), "Rules text");
      await user.click(screen.getByRole("button", { name: "Find cards" }));
      expect(router.push).toHaveBeenLastCalledWith(
        "/cards?catalog_snapshot_id=snap-1&limit=24",
      );
      await user.type(
        screen.getByRole("searchbox", { name: "Name, type or text" }),
        "flying{Enter}",
      );
      expect(router.push).toHaveBeenLastCalledWith(
        "/cards?in=text&q=flying&catalog_snapshot_id=snap-1&limit=24",
      );
    });

    it("submits from the search field with Enter", async () => {
      const user = userEvent.setup();
      render(<Filters snapshot={snapshot} query="" />);
      await user.type(
        screen.getByRole("searchbox", { name: "Name, type or text" }),
        "bolt{Enter}",
      );
      expect(router.push).toHaveBeenCalledWith(
        "/cards?q=bolt&catalog_snapshot_id=snap-1&limit=24",
      );
    });

    it("shows progress until the navigation settles", async () => {
      const user = userEvent.setup();
      let settle = () => {};
      router.push.mockReturnValue(
        new Promise<void>((resolve) => {
          settle = resolve;
        }),
      );
      render(<Filters snapshot={snapshot} query="" />);
      await user.click(screen.getByRole("button", { name: "Find cards" }));

      const busy = screen.getByRole("button", { name: "Searching…" });
      expect(busy).toBeDisabled();
      expect(within(busy.parentElement!).getByRole("status")).toHaveTextContent(
        "Loading matching cards…",
      );

      await act(() => {
        settle();
        return Promise.resolve();
      });

      expect(screen.getByRole("button", { name: "Find cards" })).toBeEnabled();
      expect(screen.getByRole("status")).toBeEmptyDOMElement();
    });
  });
});
