import { describe, expect, it } from "vitest";
import {
  ago,
  count,
  dateWindow,
  dateWithYear,
  deltaTone,
  grade,
  gradeTone,
  lift,
  liftTone,
  movement,
  perDollar,
  percent,
  share,
  signed,
  usd,
  windowLabel,
} from "./format";

const MINUS = "−";

describe("count", () => {
  it("groups thousands", () => {
    expect(count(0)).toBe("0");
    expect(count(999)).toBe("999");
    expect(count(33512)).toBe("33,512");
    expect(count(1_234_567)).toBe("1,234,567");
  });

  it("uses the true minus sign for negatives", () => {
    expect(count(-1234)).toBe(`${MINUS}1,234`);
    expect(count(-1234)).not.toContain("-");
  });

  it("keeps up to three fraction digits", () => {
    expect(count(1234.5678)).toBe("1,234.568");
  });
});

describe("signed", () => {
  it("prefixes positive deltas with a plus", () => {
    expect(signed(2.4)).toBe("+2.4");
    expect(signed(2.45)).toBe("+2.5");
    expect(signed(100)).toBe("+100.0");
  });

  it("uses the true minus sign for negative deltas", () => {
    expect(signed(-0.8)).toBe(`${MINUS}0.8`);
    expect(signed(-12.34)).toBe(`${MINUS}12.3`);
  });

  it("shows values that round to zero as an unsigned zero", () => {
    expect(signed(0)).toBe("0.0");
    expect(signed(-0)).toBe("0.0");
    expect(signed(0.049)).toBe("0.0");
    expect(signed(-0.049)).toBe("0.0");
  });

  it("starts signing at the ±0.05 rounding boundary", () => {
    expect(signed(0.05)).toBe("+0.1");
    expect(signed(-0.05)).toBe(`${MINUS}0.1`);
  });
});

describe("percent", () => {
  it("formats percentage points with one decimal", () => {
    expect(percent(54.12)).toBe("54.1%");
    expect(percent(100)).toBe("100.0%");
    expect(percent(0)).toBe("0.0%");
  });

  it("never shows a negative zero", () => {
    expect(percent(-0.04)).toBe("0.0%");
    expect(percent(-3.25)).toBe(`${MINUS}3.3%`);
  });
});

describe("lift", () => {
  it("formats ratios with two decimals and a multiplication sign", () => {
    expect(lift(1.123)).toBe("1.12×");
    expect(lift(1)).toBe("1.00×");
    expect(lift(0)).toBe("0.00×");
    expect(lift(0.004)).toBe("0.00×");
  });

  it("uses the true minus sign for negative ratios", () => {
    expect(lift(-0.5)).toBe(`${MINUS}0.50×`);
  });
});

describe("usd", () => {
  it("shows dollars and cents with thousands separators", () => {
    expect(usd(0.6)).toBe("$0.60");
    expect(usd(0.05)).toBe("$0.05");
    expect(usd(1125.91)).toBe("$1,125.91");
  });
});

describe("perDollar", () => {
  it("shows whole numbers from 100 and three figures below", () => {
    expect(perDollar(1666.67)).toBe("1,667");
    expect(perDollar(166.67)).toBe("167");
    expect(perDollar(41.234)).toBe("41.2");
    expect(perDollar(2.2711)).toBe("2.27");
    expect(perDollar(0.0621)).toBe("0.0621");
  });
});

describe("dateWithYear", () => {
  it("names an instant's UTC day", () => {
    expect(dateWithYear("2026-09-27T21:05:46.301Z")).toBe("Sep 27, 2026");
    expect(dateWithYear("2026-09-27T23:59:59-03:00")).toBe("Sep 28, 2026");
  });
});

describe("movement", () => {
  it("shows places gained, lost or unchanged", () => {
    expect(movement(3)).toBe("▲ 3");
    expect(movement(-2)).toBe("▼ 2");
    expect(movement(0)).toBe("—");
  });

  it("treats a missing number as unchanged", () => {
    expect(movement(Number.NaN)).toBe("—");
  });
});

describe("deltaTone", () => {
  it("is neutral strictly inside ±0.05 points", () => {
    expect(deltaTone(0)).toBe("neutral");
    expect(deltaTone(0.0499)).toBe("neutral");
    expect(deltaTone(-0.0499)).toBe("neutral");
  });

  it("signals from ±0.05 points inclusive", () => {
    expect(deltaTone(0.05)).toBe("positive");
    expect(deltaTone(7)).toBe("positive");
    expect(deltaTone(-0.05)).toBe("negative");
    expect(deltaTone(-7)).toBe("negative");
  });

  it("agrees with signed() on when a delta has a sign", () => {
    for (const value of [-0.06, -0.05, -0.04, 0, 0.04, 0.05, 0.06]) {
      const text = signed(value);
      const tone = deltaTone(value);
      expect(tone === "positive").toBe(text.startsWith("+"));
      expect(tone === "negative").toBe(text.startsWith(MINUS));
    }
  });
});

describe("liftTone", () => {
  it("is positive from 1.10× inclusive", () => {
    expect(liftTone(1.1)).toBe("positive");
    expect(liftTone(2)).toBe("positive");
    expect(liftTone(1.0999)).toBe("neutral");
  });

  it("is negative strictly below 0.97×", () => {
    expect(liftTone(0.97)).toBe("neutral");
    expect(liftTone(0.9699)).toBe("negative");
    expect(liftTone(0)).toBe("negative");
  });

  it("is neutral around an even ratio", () => {
    expect(liftTone(1)).toBe("neutral");
  });
});

describe("grade", () => {
  it.each([
    [100, "A+"],
    [90, "A+"],
    [89.99, "A"],
    [85, "A"],
    [80, `A${MINUS}`],
    [75, "B+"],
    [70, "B"],
    [65, `B${MINUS}`],
    [60, "C+"],
    [59.9, "C"],
    [50, "C"],
    [45, `C${MINUS}`],
    [44.9, "D"],
    [35, "D"],
    [34.9, "F"],
    [0, "F"],
  ])("grades %s as %s", (score, letter) => {
    expect(grade(score)).toBe(letter);
  });

  it("clamps out-of-range scores to the outer grades", () => {
    expect(grade(150)).toBe("A+");
    expect(grade(-10)).toBe("F");
    expect(grade(Number.NaN)).toBe("F");
  });
});

describe("gradeTone", () => {
  it("maps each letter family to its tone", () => {
    expect(gradeTone("A+")).toBe("a");
    expect(gradeTone(`A${MINUS}`)).toBe("a");
    expect(gradeTone("B")).toBe("b");
    expect(gradeTone(`C${MINUS}`)).toBe("c");
    expect(gradeTone("D")).toBe("d");
    expect(gradeTone("F")).toBe("f");
  });

  it("covers every grade() can return", () => {
    for (let score = -5; score <= 105; score += 0.5)
      expect(["a", "b", "c", "d", "f"]).toContain(gradeTone(grade(score)));
  });
});

describe("share", () => {
  it("is the part's percentage of the whole with one decimal", () => {
    expect(share(37, 231)).toBe("16.0%");
    expect(share(231, 231)).toBe("100.0%");
    expect(share(0, 231)).toBe("0.0%");
  });

  it("has no share of an empty whole", () => {
    expect(share(0, 0)).toBe("—");
  });
});

describe("dateWindow", () => {
  it("shows the exclusive end as the last included day", () => {
    expect(dateWindow("2026-03-01", "2026-09-01")).toBe("Mar 1 – Aug 31, 2026");
  });

  it("names both years when the window crosses one", () => {
    expect(dateWindow("2025-12-01", "2026-03-01")).toBe(
      "Dec 1, 2025 – Feb 28, 2026",
    );
  });

  it("is independent of the local time zone", () => {
    expect(dateWindow("2026-01-01", "2026-01-02")).toBe("Jan 1 – Jan 1, 2026");
  });
});

describe("ago", () => {
  const now = new Date("2026-10-19T12:00:00Z");

  it("names the largest whole unit that has passed", () => {
    expect(ago("2026-10-19T09:59:00Z", now)).toBe("2 hours ago");
    expect(ago("2026-10-19T11:15:00Z", now)).toBe("45 minutes ago");
    expect(ago("2026-10-16T12:00:00Z", now)).toBe("3 days ago");
    expect(ago("2026-09-28T12:00:00Z", now)).toBe("3 weeks ago");
    expect(ago("2026-06-01T12:00:00Z", now)).toBe("4 months ago");
    expect(ago("2024-01-01T00:00:00Z", now)).toBe("2 years ago");
  });

  it("says yesterday, last week and last month for a single unit", () => {
    expect(ago("2026-10-18T06:00:00Z", now)).toBe("yesterday");
    expect(ago("2026-10-12T12:00:00Z", now)).toBe("last week");
    expect(ago("2026-09-15T12:00:00Z", now)).toBe("last month");
  });

  it("reads under a minute, or a clock behind the publisher, as just now", () => {
    expect(ago("2026-10-19T11:59:30Z", now)).toBe("just now");
    expect(ago("2026-10-19T12:05:00Z", now)).toBe("just now");
  });

  it("measures from the current time by default", () => {
    expect(ago(new Date(Date.now() - 3 * 3_600_000).toISOString())).toBe(
      "3 hours ago",
    );
  });
});

describe("windowLabel", () => {
  it("names a recent window by its length and a long one by its start", () => {
    expect(windowLabel("2026-07-03", "2026-10-01", "2026-10-01")).toBe(
      "Last 90 days",
    );
    expect(windowLabel("2024-01-01", "2026-10-01", "2026-10-01")).toBe(
      "Since Jan 1, 2024",
    );
  });

  it("gives an older window its dates", () => {
    expect(windowLabel("2026-03-01", "2026-09-01", "2026-10-01")).toBe(
      "Mar 1 – Aug 31, 2026",
    );
  });
});
