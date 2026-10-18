import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { setPathname } from "@/test/navigation";
import { SectionTag, SiteNav } from "./site-nav";

describe("SiteNav", () => {
  it("links to each section from the main navigation", () => {
    render(<SiteNav />);
    expect(
      screen.getByRole("navigation", { name: "Main" }),
    ).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Discovery" })).toHaveAttribute(
      "href",
      "/cards",
    );
    expect(screen.getByRole("link", { name: "Methodology" })).toHaveAttribute(
      "href",
      "/datasets",
    );
  });

  it.each([
    ["/cards", "Discovery"],
    ["/cards/0b4a7c1e", "Discovery"],
    ["/datasets", "Methodology"],
    ["/datasets/snap-1", "Methodology"],
  ])("marks the current section on %s", (pathname, current) => {
    setPathname(pathname);
    render(<SiteNav />);
    for (const link of screen.getAllByRole("link"))
      if (link.textContent === current)
        expect(link).toHaveAttribute("aria-current", "page");
      else expect(link).not.toHaveAttribute("aria-current");
  });

  it("marks no section elsewhere", () => {
    setPathname("/primitives");
    render(<SiteNav />);
    for (const link of screen.getAllByRole("link"))
      expect(link).not.toHaveAttribute("aria-current");
  });
});

describe("SectionTag", () => {
  it("names the current section", () => {
    setPathname("/datasets/snap-1");
    const { container } = render(<SectionTag />);
    expect(screen.getByText("Methodology")).toHaveClass("section-tag");
    expect(container.querySelector(".brand-divider")).toHaveAttribute(
      "aria-hidden",
      "true",
    );
  });

  it("renders nothing outside a section", () => {
    setPathname("/");
    const { container } = render(<SectionTag />);
    expect(container).toBeEmptyDOMElement();
  });
});
