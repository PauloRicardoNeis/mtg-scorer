import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import type { RankedCard, RankingPage } from "@/lib/api";
import { english } from "@/test/i18n";
import {
  GradeRing,
  MetaShare,
  MostPlayedIn,
  RankMove,
  TopCutLift,
  Trend,
  WinRate,
  defaultMethod,
  isGraded,
  percentile,
  shares,
  trendLabel,
} from "./ranking-data";

const run = {
  series_period_days: 30,
  series_decks: [0, 0, 0, 0, 0, 0, 0, 0, 0, 2, 0, 5],
} as RankingPage["score_run"];

function card(overrides: Partial<RankedCard>): RankedCard {
  return {
    archetype_count: 2,
    archetype_deck_count: 3,
    archetype_label: "Burn",
    archetypes: [{ label: "Burn", deck_count: 3, colors: ["R"] }],
    series_decks: [0, 0, 0, 0, 0, 0, 0, 0, 0, 1, 0, 4],
    share_delta: 0.3,
    win_rate: 0.55,
    win_rate_delta: 0.031,
    ...overrides,
  } as RankedCard;
}

describe("isGraded and defaultMethod", () => {
  const methods = (...ids: string[]) =>
    ({
      methods: ids.map((method_id) => ({ method_id })),
    }) as RankingPage["score_run"];

  it("grades the percentile scores and not relative volume", () => {
    expect(isGraded("constructed-score")).toBe(true);
    expect(isGraded("signature-score")).toBe(true);
    expect(isGraded("max-ratio")).toBe(false);
  });

  it("defaults to the constructed score, then volume, then the run's first", () => {
    expect(
      defaultMethod(
        methods("max-ratio", "signature-score", "constructed-score"),
      ),
    ).toBe("constructed-score");
    expect(defaultMethod(methods("signature-score", "max-ratio"))).toBe(
      "max-ratio",
    );
    expect(defaultMethod(methods("foundation"))).toBe("foundation");
  });
});

describe("GradeRing", () => {
  it.each([
    [95, "A+", "ring-a"],
    [72, "B", "ring-b"],
    [55, "C", "ring-c"],
    [40, "D", "ring-d"],
    [10, "F", "ring-f"],
  ])("fills %d as %s", (score, letter, tone) => {
    const { container } = render(<GradeRing score={score} size="compare" />);
    expect(screen.getByLabelText(`Grade ${letter}`)).toHaveTextContent(letter);
    const ring = container.firstElementChild as HTMLElement;
    expect(ring).toHaveClass("grade-ring-compare", tone);
    expect(ring.style.getPropertyValue("--fill")).toBe(`${score * 3.6}deg`);
  });

  it("clamps the fill and shows an unknown score as a dash", () => {
    const { container, rerender } = render(<GradeRing score={140} />);
    expect(
      (container.firstElementChild as HTMLElement).style.getPropertyValue(
        "--fill",
      ),
    ).toBe("360deg");
    rerender(<GradeRing score={null} size="preview" />);
    expect(screen.getByLabelText("No grade")).toHaveTextContent("—");
    expect(container.firstElementChild).toHaveClass(
      "grade-ring-unknown",
      "grade-ring-preview",
    );
  });
});

describe("RankMove", () => {
  it.each([
    [3, "▲ 3", "Up 3 places", "rank-move-up"],
    [1, "▲ 1", "Up 1 place", "rank-move-up"],
    [-2, "▼ 2", "Down 2 places", "rank-move-down"],
    [0, "—", "Same rank as before", "rank-move-flat"],
  ])("reads %d as %s", (change, mark, spoken, tone) => {
    const { container } = render(<RankMove change={change} />);
    expect(container.firstElementChild).toHaveClass(tone);
    expect(container).toHaveTextContent(mark + spoken);
  });

  it("says when there is no earlier rank", () => {
    const { container, rerender } = render(<RankMove change={null} />);
    expect(container).toHaveTextContent("No earlier rank");
    rerender(<RankMove change={undefined} />);
    expect(container).toHaveTextContent("No earlier rank");
  });
});

describe("WinRate", () => {
  it("grows right for a positive delta and left for a negative one", () => {
    const { container, rerender } = render(<WinRate card={card({})} />);
    const fill = () => container.querySelector<HTMLElement>(".diverging-fill")!;
    expect(fill()).toHaveClass("above");
    expect(fill().style.left).toBe("36px");
    expect(container).toHaveTextContent("+3.1% against the field55.0% WR");
    rerender(<WinRate card={card({ win_rate: 0.4, win_rate_delta: -0.12 })} />);
    expect(fill()).toHaveClass("below");
    expect(fill().style.left).toBe("0px");
    expect(fill().style.width).toBe("36px");
    rerender(<WinRate card={card({ win_rate: 0.5, win_rate_delta: 0 })} />);
    expect(fill().style.width).toBe("1.5px");
  });

  it("is unknown without a record", () => {
    render(<WinRate card={card({ win_rate: null, win_rate_delta: null })} />);
    expect(screen.getByText("Unknown")).toBeInTheDocument();
  });
});

describe("MetaShare and TopCutLift", () => {
  it("sizes the share against the leading card", () => {
    const { container, rerender } = render(
      <MetaShare decks={2} total={8} most={4} />,
    );
    expect(container).toHaveTextContent("25.0%");
    expect(
      container
        .querySelector<HTMLElement>(".share-bar")!
        .style.getPropertyValue("--fill"),
    ).toBe("50%");
    rerender(<MetaShare decks={2} total={0} most={0} />);
    expect(container).toHaveTextContent("—");
    expect(
      container
        .querySelector<HTMLElement>(".share-bar")!
        .style.getPropertyValue("--fill"),
    ).toBe("0%");
  });

  it("tones the lift and keeps an unknown one unknown", () => {
    const { container, rerender } = render(<TopCutLift value={0.9} />);
    expect(container.firstElementChild).toHaveClass("tone-negative");
    rerender(<TopCutLift value={null} />);
    expect(container).toHaveTextContent("Unknown");
  });
});

describe("Trend", () => {
  it("draws known periods and colors the change", () => {
    const { container, rerender } = render(<Trend card={card({})} run={run} />);
    expect(container.firstElementChild).toHaveClass("trend-up");
    expect(container.querySelector("path")!.getAttribute("d")).toMatch(
      /^M52\.4 \d/,
    );
    expect(container).toHaveTextContent("+30.0 points of meta share");
    rerender(<Trend card={card({ share_delta: -0.01 })} run={run} />);
    expect(container.firstElementChild).toHaveClass("trend-down");
    rerender(<Trend card={card({ share_delta: 0.001 })} run={run} />);
    expect(container.firstElementChild).toHaveClass("trend-flat");
  });

  it("draws a flat series without dividing by zero", () => {
    const { container } = render(
      <Trend
        card={card({ series_decks: [0, 0, 0, 0, 0, 0, 0, 0, 0, 2, 0, 5] })}
        run={run}
      />,
    );
    expect(container.querySelector("path")!.getAttribute("d")).toBe(
      "M52.4 21.0 L64.0 21.0",
    );
  });

  it("shows a dash with fewer than two known periods or no change", () => {
    const { container, rerender } = render(
      <Trend card={card({ share_delta: null })} run={run} />,
    );
    expect(container).toHaveTextContent("—");
    rerender(<Trend card={card({ series_decks: null })} run={run} />);
    expect(container).toHaveTextContent("—");
  });

  it("finds no shares without the run's series", () => {
    expect(shares(card({}), { ...run, series_decks: null })).toEqual([]);
  });
});

describe("trendLabel", () => {
  it("reads the series reach in months or weeks", () => {
    expect(trendLabel(run, english)).toBe("12 mo");
    expect(trendLabel({ ...run, series_period_days: 16 }, english)).toBe(
      "6 mo",
    );
    expect(trendLabel({ ...run, series_period_days: 3 }, english)).toBe("5 wk");
    expect(
      trendLabel({ ...run, series_period_days: null }, english),
    ).toBeNull();
    expect(trendLabel({ ...run, series_decks: null }, english)).toBeNull();
  });
});

describe("MostPlayedIn", () => {
  it("shows the leading archetype with its colors and how many others play the card", () => {
    const { container } = render(<MostPlayedIn card={card({})} />);
    expect(container).toHaveTextContent("Burn+1 more archetype");
    expect(
      container.querySelector('.color-pips img[src$="/R.svg"]'),
    ).not.toBeNull();
  });

  it("falls back to the label, then to unlabelled", () => {
    const { container, rerender } = render(
      <MostPlayedIn card={card({ archetypes: [], archetype_count: null })} />,
    );
    expect(container).toHaveTextContent("Burn");
    rerender(
      <MostPlayedIn
        card={card({
          archetypes: [],
          archetype_label: null,
          archetype_count: 0,
        })}
      />,
    );
    expect(container).toHaveTextContent("Unlabelled");
  });

  it("counts other archetypes from the list when the total is unknown", () => {
    const { container } = render(
      <MostPlayedIn
        card={card({
          archetype_count: null,
          archetypes: [
            { label: "Burn", deck_count: 3, colors: ["R"] },
            { label: "Prowess", deck_count: 1, colors: [] },
          ],
        })}
      />,
    );
    expect(container).toHaveTextContent("Burn+1");
  });
});

describe("percentile", () => {
  it("rounds up to a whole percent of at least 1", () => {
    expect(percentile(1, 8, english)).toBe("Top 13%");
    expect(percentile(1, 939, english)).toBe("Top 1%");
    expect(percentile(1, 0, english)).toBeNull();
  });
});
