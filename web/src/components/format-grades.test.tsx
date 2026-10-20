import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { FormatGradeRows, FormatGrades } from "./format-grades";

const formats = [
  { format_name: "Legacy", score: 98.6 },
  { format_name: "EDH", score: 72 },
  { format_name: "Modern", score: 30 },
];

describe("FormatGrades", () => {
  it("names the leading formats with their letters and counts the rest", () => {
    const { container } = render(<FormatGrades formats={formats} />);
    expect(container).toHaveTextContent("LegacyA+CommanderB+1 more format");
    expect(screen.getByText("A+")).toHaveClass("tone-a");
  });

  it("shows every format when they fit", () => {
    const { container } = render(<FormatGrades formats={formats} shown={3} />);
    expect(container).toHaveTextContent("LegacyA+CommanderBModernF");
    expect(container).not.toHaveTextContent("more");
  });

  it("reads a format run's missing grades as unknown", () => {
    const { container } = render(<FormatGrades formats={null} />);
    expect(container).toHaveTextContent("—");
  });
});

describe("FormatGradeRows", () => {
  it("lists every format with its letter, score and a bar of the score", () => {
    const { container } = render(<FormatGradeRows formats={formats} />);
    const rows = container.querySelectorAll(".played-row");
    expect([...rows].map((row) => row.textContent)).toEqual([
      "A+Legacy98.6",
      "BCommander72.0",
      "FModern30.0",
    ]);
    expect(
      (
        rows[1].querySelector(".played-bar") as HTMLElement
      ).style.getPropertyValue("--fill"),
    ).toBe("72%");
  });

  it("says so when there are no format grades", () => {
    render(<FormatGradeRows formats={[]} />);
    expect(screen.getByText("No format grades")).toBeInTheDocument();
  });
});
