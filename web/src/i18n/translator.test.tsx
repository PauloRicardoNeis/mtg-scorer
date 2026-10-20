import { render } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { de } from "./messages/de";
import { en } from "./messages/en";
import { ru } from "./messages/ru";
import { spaced } from "@/test/i18n";
import { createI18n } from "./translator";

const english = createI18n("en", en);
const german = createI18n("de", de);
const russian = createI18n("ru", ru);
const NBSP = " ";
const MINUS = "−";

describe("fill", () => {
  it("fills named placeholders, numbers in the locale's digits", () => {
    expect(
      english.fill("{first}–{last} of {count}", {
        first: 1,
        last: 25,
        count: 1234,
      }),
    ).toBe("1–25 of 1,234");
    expect(german.fill("{count} Decks", { count: 1234 })).toBe("1.234 Decks");
    expect(english.fill("Open {format} rankings", { format: "Modern" })).toBe(
      "Open Modern rankings",
    );
  });

  it("leaves a placeholder without a value as written", () => {
    expect(english.fill("Rank {rank}: {name}", { rank: 3 })).toBe(
      "Rank 3: {name}",
    );
  });
});

describe("plural", () => {
  it("picks the locale's form for the count", () => {
    expect(english.plural(en.cards.eligiblePrintings, 1)).toBe(
      "1 eligible printing",
    );
    expect(english.plural(en.cards.eligiblePrintings, 2)).toBe(
      "2 eligible printings",
    );
    const forms = {
      one: "{count} one",
      few: "{count} few",
      many: "{count} many",
      other: "{count} other",
    };
    expect([1, 3, 5, 21, 1.5].map((n) => russian.plural(forms, n))).toEqual([
      "1 one",
      "3 few",
      "5 many",
      "21 one",
      "1,5 other",
    ]);
  });

  it("falls back to the other form when the language's form is missing", () => {
    expect(russian.plural({ other: "{count} всего" }, 3)).toBe("3 всего");
  });

  it("fills values besides the count", () => {
    expect(english.plural(en.rankings.range, 8, { first: 1, last: 8 })).toBe(
      "1–8 of 8 ranked cards",
    );
    expect(english.plural(en.rankings.range, 1, { first: 1, last: 1 })).toBe(
      "1–1 of 1 ranked card",
    );
  });
});

describe("rich", () => {
  it("puts elements where their placeholders are", () => {
    const { container } = render(
      <p>
        {english.rich(en.layout.sources, {
          topdeck: <a href="https://topdeck.gg">TopDeck.gg</a>,
        })}
      </p>,
    );
    expect(container).toHaveTextContent(
      "Card metadata and images: Scryfall. Tournament data: TopDeck.gg.",
    );
    expect(container.querySelector("a")).toHaveTextContent("TopDeck.gg");
  });

  it("keeps a placeholder without an element as written", () => {
    const { container } = render(<p>{english.rich("Updated {time}", {})}</p>);
    expect(container).toHaveTextContent("Updated {time}");
  });
});

describe("term", () => {
  it("lowercases a name mid-sentence except where nouns keep capitals", () => {
    expect(english.term("Relative volume")).toBe("relative volume");
    expect(german.term("Relatives Volumen")).toBe("Relatives Volumen");
  });
});

describe("method", () => {
  const run = {
    method_id: "max-ratio",
    label: "Relative volume",
    description: "A card's count, relative to the most played.",
  };

  it("uses the language's own words for a known method", () => {
    expect(german.method(run)).toEqual(de.methods["max-ratio"]);
  });

  it("keeps the run's words in English and for unknown methods", () => {
    expect(english.method(run)).toEqual({
      label: run.label,
      description: run.description,
    });
    expect(german.method({ ...run, method_id: "new-method" }).label).toBe(
      "Relative volume",
    );
  });
});

describe("colors", () => {
  it("names each color in order", () => {
    expect(english.colors(["W", "U"])).toBe("White · Blue");
    expect(german.colors(["W", "U"])).toBe(`${de.colors.W} · ${de.colors.U}`);
  });

  it("names colorless and unknown identities", () => {
    expect(english.colors([])).toBe("Colorless");
    expect(english.colors(null)).toBe("Unknown color identity");
  });

  it("keeps a symbol it cannot name", () => {
    expect(english.colors(["W", "P"])).toBe("White · P");
  });
});

describe("numbers", () => {
  it("formats the locale's way", () => {
    expect(english.count(33512)).toBe("33,512");
    expect(german.count(33512)).toBe("33.512");
    expect(german.decimal(87.25, 1)).toBe("87,3");
    expect(german.signed(-0.8)).toBe(`${MINUS}0,8`);
    expect(german.percent(54.12)).toBe(`54,1${NBSP}%`);
    expect(german.lift(1.123)).toBe("1,12×");
    expect(german.share(37, 231)).toBe(`16,0${NBSP}%`);
    expect(english.usd(1125.9)).toBe("$1,125.90");
    expect(english.perDollar(1666.7)).toBe("1,667");
  });
});

describe("dates", () => {
  it("formats windows, days and instants the locale's way", () => {
    expect(spaced(english.dateWindow("2026-03-01", "2026-09-01"))).toBe(
      "Mar 1 – Aug 31, 2026",
    );
    expect(spaced(german.dateWindow("2026-03-01", "2026-09-01"))).toBe(
      "1. März – 31. Aug. 2026",
    );
    expect(english.dateWithYear("2026-09-27T10:00:00Z")).toBe("Sep 27, 2026");
    expect(spaced(english.dateTime("2026-10-19T12:00:00Z"))).toBe(
      "October 19, 2026 at 12:00 PM UTC",
    );
  });
});

describe("windowLabel", () => {
  it("names a latest window of up to 120 days by its length", () => {
    expect(english.windowLabel("2026-06-03", "2026-09-01", "2026-09-01")).toBe(
      "Last 90 days",
    );
    expect(english.windowLabel("2026-08-31", "2026-09-01", "2026-09-01")).toBe(
      "Last 1 day",
    );
    expect(english.windowLabel("2026-05-04", "2026-09-01", "2026-09-01")).toBe(
      "Last 120 days",
    );
  });

  it("names a longer latest window by its start", () => {
    expect(english.windowLabel("2024-01-01", "2026-09-01", "2026-09-01")).toBe(
      "Since Jan 1, 2024",
    );
  });

  it("names an earlier window by its dates", () => {
    expect(
      spaced(english.windowLabel("2026-03-01", "2026-09-01", "2026-10-01")),
    ).toBe("Mar 1 – Aug 31, 2026");
  });
});

describe("ago", () => {
  const now = new Date("2026-10-19T12:00:00Z");

  it("says how long ago in the locale", () => {
    expect(english.ago("2026-10-19T09:59:00Z", now)).toBe("2 hours ago");
    expect(german.ago("2026-10-19T09:59:00Z", now)).toBe("vor 2 Stunden");
  });

  it("says just now under a minute", () => {
    expect(english.ago("2026-10-19T11:59:30Z", now)).toBe("just now");
    expect(german.ago("2026-10-19T11:59:30Z", now)).toBe(de.time.justNow);
  });
});
