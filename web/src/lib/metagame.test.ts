import { describe, expect, it } from "vitest";
import { en } from "@/i18n/messages/en";
import { designFormats } from "./formats";
import {
  DECK_EVENTS,
  DECK_FINISHES,
  DECK_SORTS,
  deckFormatFromId,
  type EventKind,
  finishKey,
  METAGAME_SOURCES,
  METAGAME_WINDOWS,
} from "./metagame";

describe("deckFormatFromId", () => {
  it("names the format a decklist id starts with, as rankings uses it", () => {
    expect(deckFormatFromId("modern.0.3")).toBe("Modern");
    expect(deckFormatFromId("edh.2.1")).toBe("EDH");
    expect(deckFormatFromId("pauper.12.0")).toBe("Pauper");
  });

  it("reads the prefix in any case", () => {
    expect(deckFormatFromId("Modern.0.3")).toBe("Modern");
    expect(deckFormatFromId("EDH.2.1")).toBe("EDH");
    expect(deckFormatFromId("VINTAGE.0.0")).toBe("Vintage");
  });

  it("recognizes every design format", () => {
    for (const [, format] of designFormats)
      expect(deckFormatFromId(`${format.toLowerCase()}.0.0`)).toBe(format);
  });

  it("goes by the format's name, not the tab's label", () => {
    expect(deckFormatFromId("commander.0.0")).toBeNull();
  });

  it("is null for an id outside the formats", () => {
    expect(deckFormatFromId("premodern.0.1")).toBeNull();
    expect(deckFormatFromId("0.3")).toBeNull();
    expect(deckFormatFromId(".0.3")).toBeNull();
    expect(deckFormatFromId("")).toBeNull();
  });

  it("reads only the segment before the first dot", () => {
    expect(deckFormatFromId("modern")).toBe("Modern");
    expect(deckFormatFromId("modern.legacy.0")).toBe("Modern");
    expect(deckFormatFromId("modern-0-3")).toBeNull();
  });
});

describe("finishKey", () => {
  it.each([
    ["1st", "first"],
    ["2nd", "second"],
    ["3rd", "third"],
    ["4th", "fourth"],
    ["5th", "fifth"],
    ["6th", "sixth"],
    ["7th", "seventh"],
    ["8th", "eighth"],
    ["Top 4", "top4"],
    ["Top 8", "top8"],
    ["Top 16", "top16"],
    ["Trophy", "trophy"],
  ])("keys %s as %s", (finish, key) => {
    expect(finishKey(finish)).toBe(key);
  });

  it("round-trips every finish the English messages word", () => {
    for (const [key, finish] of Object.entries(en.metagame.finishes))
      expect(finishKey(finish)).toBe(key);
  });

  it("leaves a record shown as published to the caller", () => {
    expect(finishKey("5-0")).toBeNull();
    expect(finishKey("4-1-2")).toBeNull();
  });

  it("is null for a name every object answers to", () => {
    expect(finishKey("constructor")).toBeNull();
    expect(finishKey("toString")).toBeNull();
  });

  it("is null for a finish the site has no words for", () => {
    expect(finishKey("9th")).toBeNull();
    expect(finishKey("Top 32")).toBeNull();
    expect(finishKey("")).toBeNull();
  });

  it("matches the published wording exactly", () => {
    expect(finishKey("top 8")).toBeNull();
    expect(finishKey("Top8")).toBeNull();
    expect(finishKey("1ST")).toBeNull();
    expect(finishKey(" 1st")).toBeNull();
  });
});

describe("the filter choices", () => {
  it("word every window", () => {
    for (const window of METAGAME_WINDOWS)
      expect(en.metagame.windows[window]).toBeTruthy();
  });

  it("list the sources, events, finishes and sorts the search params accept", () => {
    expect(METAGAME_SOURCES).toEqual(["all", "online", "paper"]);
    expect(DECK_EVENTS).toEqual(["challenge", "league", "paper"]);
    expect(DECK_FINISHES).toEqual(["top4", "winner"]);
    expect(DECK_SORTS).toEqual(["newest", "finish", "price_desc", "price_asc"]);
  });

  it("name an event kind a deck can come from", () => {
    const kinds: readonly EventKind[] = DECK_EVENTS;
    expect(kinds).toContain("league");
  });

  it("repeat no choice", () => {
    for (const choices of [
      METAGAME_WINDOWS,
      METAGAME_SOURCES,
      DECK_EVENTS,
      DECK_FINISHES,
      DECK_SORTS,
    ])
      expect(new Set<string>(choices).size).toBe(choices.length);
  });
});
