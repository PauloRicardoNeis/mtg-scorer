import { render, screen, within } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { FormatBar } from "./format-bar";

const tabs = [
  { label: "Standard", format: "Standard", decks: 114 },
  { label: "Pioneer", format: "Pioneer", decks: null },
  { label: "Legacy", format: "Legacy", decks: 2936 },
  { label: "Commander", format: "EDH", decks: 83339 },
];

function bar() {
  return within(screen.getByRole("navigation", { name: "Formats" }));
}

describe("FormatBar", () => {
  it("shows each format with its decks, and those without data disabled", () => {
    render(<FormatBar tabs={tabs} current="Legacy" />);
    expect(
      bar()
        .getAllByRole("link")
        .map((link) => link.textContent),
    ).toEqual([
      "Standard114 decks",
      "PioneerNo data yet",
      "Legacy2.9k decks",
      "Commander83k decks",
      "All formatsCompare",
    ]);
    expect(bar().getByRole("link", { name: /Legacy/ })).toHaveAttribute(
      "aria-current",
      "page",
    );
    const pioneer = bar().getByRole("link", { name: /Pioneer/ });
    expect(pioneer).toHaveAttribute("aria-disabled", "true");
    expect(pioneer).toHaveAttribute("tabindex", "-1");
    expect(bar().getByRole("link", { name: /Commander/ })).toHaveAttribute(
      "href",
      "/rankings?format=EDH",
    );
  });

  it("carries the reader's grading to every format and only its own to compare", () => {
    const { rerender } = render(
      <FormatBar tabs={tabs} current="Legacy" query="method=max-ratio" />,
    );
    expect(bar().getByRole("link", { name: /Commander/ })).toHaveAttribute(
      "href",
      "/rankings?format=EDH&method=max-ratio",
    );
    expect(bar().getByRole("link", { name: /All formats/ })).toHaveAttribute(
      "href",
      "/rankings/compare",
    );
    rerender(
      <FormatBar
        tabs={tabs}
        current="Legacy"
        query="method=signature-score"
        compareQuery="method=signature-score"
      />,
    );
    expect(bar().getByRole("link", { name: /All formats/ })).toHaveAttribute(
      "href",
      "/rankings/compare?method=signature-score",
    );
  });

  it("leaves the reader's grading behind on the overall tab", () => {
    render(
      <FormatBar
        tabs={[
          { label: "Overall", format: "Overall", decks: 92506, overall: true },
          ...tabs,
        ]}
        current="Legacy"
        query="method=signature-score"
      />,
    );
    const overall = bar().getByRole("link", { name: /Overall/ });
    expect(overall).toHaveAttribute("href", "/rankings?format=Overall");
    expect(overall).toHaveTextContent("Overall93k decks");
    expect(bar().getByRole("link", { name: /Legacy/ })).toHaveAttribute(
      "href",
      "/rankings?format=Legacy&method=signature-score",
    );
  });

  it("marks the compare tab while comparing", () => {
    render(<FormatBar tabs={tabs} current={null} comparing />);
    expect(bar().getByRole("link", { name: /All formats/ })).toHaveAttribute(
      "aria-current",
      "page",
    );
    expect(bar().getByRole("link", { name: /All formats/ })).toHaveAttribute(
      "href",
      "/rankings/compare",
    );
  });

  it("scrolls the current tab clear of the faded right edge", () => {
    const rect = (left: number, right: number) =>
      ({
        left,
        right,
        top: 0,
        bottom: 0,
        width: right - left,
        height: 0,
      }) as DOMRect;
    const spy = vi
      .spyOn(HTMLElement.prototype, "getBoundingClientRect")
      .mockImplementation(function (this: HTMLElement) {
        if (this.getAttribute("aria-label") === "Formats") return rect(0, 300);
        return rect(280, 360);
      });
    render(<FormatBar tabs={tabs} current="EDH" />);
    expect(screen.getByRole("navigation", { name: "Formats" }).scrollLeft).toBe(
      100,
    );
    spy.mockRestore();
  });

  it("scrolls a tab left of the view back in", () => {
    const rect = (left: number, right: number) =>
      ({
        left,
        right,
        top: 0,
        bottom: 0,
        width: right - left,
        height: 0,
      }) as DOMRect;
    const nav = { left: 100, right: 400 };
    vi.spyOn(HTMLElement.prototype, "getBoundingClientRect").mockImplementation(
      function (this: HTMLElement) {
        if (this.getAttribute("aria-label") === "Formats")
          return rect(nav.left, nav.right);
        return rect(40, 120);
      },
    );
    const { container } = render(<FormatBar tabs={tabs} current="Standard" />);
    const element = container.querySelector("nav")!;
    // The tab starts 60px left of the bar, so the bar scrolls back by that much.
    expect(element.scrollLeft).toBe(-60);
  });

  it("leaves a visible tab where it is", () => {
    const rect = (left: number, right: number) =>
      ({
        left,
        right,
        top: 0,
        bottom: 0,
        width: right - left,
        height: 0,
      }) as DOMRect;
    vi.spyOn(HTMLElement.prototype, "getBoundingClientRect").mockImplementation(
      function (this: HTMLElement) {
        if (this.getAttribute("aria-label") === "Formats") return rect(0, 600);
        return rect(100, 200);
      },
    );
    render(<FormatBar tabs={tabs} current="Legacy" />);
    expect(screen.getByRole("navigation", { name: "Formats" }).scrollLeft).toBe(
      0,
    );
  });

  it("leaves the bar alone without a current tab", () => {
    render(<FormatBar tabs={tabs} current={null} />);
    expect(screen.getByRole("navigation", { name: "Formats" }).scrollLeft).toBe(
      0,
    );
  });
});
