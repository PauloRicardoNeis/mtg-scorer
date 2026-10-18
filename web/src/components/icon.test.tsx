import { render } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { Icon } from "./icon";

describe("Icon", () => {
  it("is decorative and hidden from assistive tech", () => {
    const { container } = render(<Icon name="search" />);
    const svg = container.querySelector("svg");
    expect(svg).toHaveAttribute("aria-hidden", "true");
    expect(svg).toHaveAttribute("focusable", "false");
    expect(svg).toHaveAttribute("viewBox", "0 0 24 24");
  });

  it("draws every path of the named icon", () => {
    const { container } = render(<Icon name="triangle-alert" />);
    expect(container.querySelectorAll("path")).toHaveLength(3);
  });

  it("defaults to 16px with a lighter stroke", () => {
    const { container } = render(<Icon name="x" />);
    const svg = container.querySelector("svg");
    expect(svg).toHaveAttribute("width", "16");
    expect(svg).toHaveAttribute("height", "16");
    expect(svg).toHaveAttribute("stroke-width", "1.75");
  });

  it("thickens the stroke at 14px and below", () => {
    const { container } = render(<Icon name="copy" size={14} />);
    const svg = container.querySelector("svg");
    expect(svg).toHaveAttribute("width", "14");
    expect(svg).toHaveAttribute("stroke-width", "2");
  });
});
