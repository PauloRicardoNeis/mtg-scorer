import { describe, expect, it } from "vitest";
import {
  count,
  deltaTone,
  grade,
  gradeTone,
  lift,
  liftTone,
  movement,
  percent,
  signed,
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
