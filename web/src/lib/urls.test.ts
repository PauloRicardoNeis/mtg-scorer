import { describe, expect, it } from "vitest";
import type { Printing } from "./api";
import {
  cardDecksHref,
  deckPageHref,
  deckParams,
  edition,
  printingParams,
  queryParams,
  rankedCardHref,
} from "./urls";

describe("queryParams", () => {
  it("returns empty params for empty input", () => {
    expect(queryParams({}).toString()).toBe("");
  });

  it("keeps single values and every value of repeated keys in order", () => {
    const query = queryParams({
      q: "bolt",
      set: ["m11", "lea"],
      rarity: "rare",
    });
    expect([...query]).toEqual([
      ["q", "bolt"],
      ["set", "m11"],
      ["set", "lea"],
      ["rarity", "rare"],
    ]);
  });

  it("skips undefined values and empty arrays but keeps empty strings", () => {
    const query = queryParams({ q: "", cursor: undefined, set: [] });
    expect([...query]).toEqual([["q", ""]]);
  });

  it("encodes unicode and reserved characters", () => {
    const query = queryParams({ q: "Æther & fire/ice", color: "W+U" });
    expect(query.toString()).toBe("q=%C3%86ther+%26+fire%2Fice&color=W%2BU");
    expect(new URLSearchParams(query.toString()).get("q")).toBe(
      "Æther & fire/ice",
    );
  });
});

describe("printingParams", () => {
  it("keeps only the filters a printing list accepts", () => {
    const result = printingParams(
      new URLSearchParams(
        "q=bolt&catalog_snapshot_id=snap-1&set=m11&set=lea&rarity=rare&color=R&game=paper&limit=24&cursor=abc&type=instant",
      ),
    );
    expect([...result]).toEqual([
      ["catalog_snapshot_id", "snap-1"],
      ["set", "m11"],
      ["set", "lea"],
      ["rarity", "rare"],
      ["game", "paper"],
      ["limit", "24"],
    ]);
  });

  it("returns empty params when nothing applies", () => {
    expect(printingParams(new URLSearchParams("q=bolt")).size).toBe(0);
  });

  it("does not modify its input", () => {
    const query = new URLSearchParams("set=m11&q=bolt");
    printingParams(query);
    expect(query.toString()).toBe("set=m11&q=bolt");
  });
});

describe("deckParams", () => {
  it("asks for the pinned run from the listed offset", () => {
    const result = deckParams(
      new URLSearchParams(
        "catalog_snapshot_id=snap-1&set=m11&decks_run=scores-a&decks_offset=40",
      ),
    );
    expect([...result]).toEqual([
      ["score_run_id", "scores-a"],
      ["offset", "40"],
    ]);
  });

  it("reads an unreadable offset as the first page", () => {
    expect(deckParams(new URLSearchParams("decks_offset=-20")).toString()).toBe(
      "",
    );
    expect(deckParams(new URLSearchParams("decks_run=")).size).toBe(0);
  });
});

describe("deck page links", () => {
  const run = `scores-${"a".repeat(64)}`;

  it("open a deck from a card, keeping its catalog and the list's page", () => {
    expect(
      deckPageHref(
        run,
        41,
        "bolt-id",
        new URLSearchParams(
          `catalog_snapshot_id=catalog-a&set=m11&decks_run=${run}&decks_offset=40`,
        ),
      ),
    ).toBe(
      `/decks/${run}/41?card=bolt-id&catalog_snapshot_id=catalog-a&decks_offset=40`,
    );
    expect(deckPageHref(run, 0, "bolt-id", new URLSearchParams())).toBe(
      `/decks/${run}/0?card=bolt-id`,
    );
  });

  it("lead back to the card's deck list in the deck's run", () => {
    expect(
      cardDecksHref(
        "bolt id",
        run,
        new URLSearchParams(
          "card=bolt&catalog_snapshot_id=catalog-a&decks_offset=40",
        ),
      ),
    ).toBe(
      `/cards/bolt%20id?catalog_snapshot_id=catalog-a&decks_run=${run}&decks_offset=40#decks`,
    );
    expect(cardDecksHref("bolt", run, new URLSearchParams())).toBe(
      `/cards/bolt?decks_run=${run}#decks`,
    );
  });
});

describe("edition", () => {
  const printing = {
    set_name: "Magic 2011",
    collector_number: "149",
    language: "en",
  } as Printing;

  it("names the set, collector number and language", () => {
    expect(edition(printing)).toBe("Magic 2011 #149 (EN)");
  });

  it("keeps unicode set names and odd collector numbers", () => {
    expect(
      edition({
        ...printing,
        set_name: "Commander Légendes",
        collector_number: "★12a",
        language: "fr",
      }),
    ).toBe("Commander Légendes #★12a (FR)");
  });
});

describe("rankedCardHref", () => {
  const card = {
    oracle_id: "4457ed35-7c10-48c8-9776-456485fdf070",
    preview_printing: {} as Printing,
  };

  it("opens the card in the catalog the ranking joined", () => {
    expect(rankedCardHref(card, "snap 1")).toBe(
      "/cards/4457ed35-7c10-48c8-9776-456485fdf070?catalog_snapshot_id=snap+1",
    );
  });

  it("has no page for a card outside the catalog or without one", () => {
    expect(rankedCardHref({ ...card, preview_printing: null }, "snap-1")).toBe(
      null,
    );
    expect(rankedCardHref(card, null)).toBe(null);
  });
});
