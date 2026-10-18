import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import { IconButton, Panel, UnderlineTabs } from "./primitives";

describe("IconButton", () => {
  it("is a plain button named by its label", () => {
    render(<IconButton icon="x" label="Dismiss" />);
    const button = screen.getByRole("button", { name: "Dismiss" });
    expect(button).toHaveAttribute("type", "button");
    expect(button).toHaveAttribute("title", "Dismiss");
    expect(button).not.toHaveAttribute("aria-pressed");
    expect(button).toHaveClass("icon-button", { exact: true });
  });

  it("reports a toggle state through aria-pressed", () => {
    const { rerender } = render(
      <IconButton icon="info" label="Details" pressed={false} />,
    );
    expect(
      screen.getByRole("button", { name: "Details", pressed: false }),
    ).toBeInTheDocument();
    rerender(<IconButton icon="info" label="Details" pressed />);
    expect(
      screen.getByRole("button", { name: "Details", pressed: true }),
    ).toBeInTheDocument();
  });

  it("adds size and custom classes and sizes the icon", () => {
    const { rerender } = render(
      <IconButton icon="x" label="Close" size="sm" className="extra" />,
    );
    const button = screen.getByRole("button", { name: "Close" });
    expect(button).toHaveClass("icon-button", "sm", "extra");
    expect(button.querySelector("svg")).toHaveAttribute("width", "14");
    rerender(<IconButton icon="x" label="Close" size="lg" />);
    expect(button).toHaveClass("icon-button lg", { exact: true });
    expect(button.querySelector("svg")).toHaveAttribute("width", "16");
  });

  it("passes button attributes and handlers through", async () => {
    const user = userEvent.setup();
    const onClick = vi.fn();
    const { rerender } = render(
      <IconButton icon="copy" label="Copy" onClick={onClick} />,
    );
    await user.click(screen.getByRole("button", { name: "Copy" }));
    expect(onClick).toHaveBeenCalledTimes(1);

    rerender(
      <IconButton icon="copy" label="Copy" onClick={onClick} disabled />,
    );
    expect(screen.getByRole("button", { name: "Copy" })).toBeDisabled();
    await user.click(screen.getByRole("button", { name: "Copy" }));
    expect(onClick).toHaveBeenCalledTimes(1);
  });
});

describe("Panel", () => {
  it("renders only its content without a header when nothing is given", () => {
    const { container } = render(<Panel>Body text</Panel>);
    const section = container.querySelector("section");
    expect(section).toHaveClass("panel", { exact: true });
    expect(section).toHaveTextContent("Body text");
    expect(container.querySelector("header")).toBeNull();
  });

  it("renders the eyebrow, a level-2 title and actions", () => {
    render(
      <Panel
        eyebrow="Dataset"
        title="Snapshot details"
        actions={<button type="button">Refresh</button>}
      >
        Body
      </Panel>,
    );
    expect(
      screen.getByRole("heading", { level: 2, name: "Snapshot details" }),
    ).toBeInTheDocument();
    expect(screen.getByText("Dataset")).toHaveClass("eyebrow");
    expect(screen.getByRole("button", { name: "Refresh" })).toBeInTheDocument();
  });

  it("uses a level-3 heading when nested", () => {
    render(<Panel title="Nested" level={3} />);
    expect(
      screen.getByRole("heading", { level: 3, name: "Nested" }),
    ).toBeInTheDocument();
  });

  it("shows a header for actions alone", () => {
    const { container } = render(
      <Panel actions={<a href="/cards">All cards</a>} />,
    );
    expect(container.querySelector("header")).toBeInTheDocument();
    expect(screen.queryByRole("heading")).toBeNull();
  });

  it("adds the grid pattern and custom classes", () => {
    const { container } = render(<Panel pattern className="wide" />);
    expect(container.querySelector("section")).toHaveClass(
      "panel",
      "grid-pattern",
      "wide",
    );
  });
});

describe("UnderlineTabs", () => {
  const items = [
    { href: "/cards/1?view=overview", label: "Overview", current: true },
    { href: "/cards/1?view=printings", label: "Printings", count: 12 },
    { href: "/cards/1?view=decks", label: "Decks", count: 0, disabled: true },
  ];

  it("renders a labelled navigation of links", () => {
    render(<UnderlineTabs label="Card views" items={items} />);
    const nav = screen.getByRole("navigation", { name: "Card views" });
    expect(nav).toBeInTheDocument();
    expect(screen.getAllByRole("link")).toHaveLength(3);
    expect(screen.getByRole("link", { name: "Overview" })).toHaveAttribute(
      "href",
      "/cards/1?view=overview",
    );
  });

  it("marks only the current tab", () => {
    render(<UnderlineTabs label="Card views" items={items} />);
    expect(screen.getByRole("link", { name: "Overview" })).toHaveAttribute(
      "aria-current",
      "page",
    );
    expect(screen.getByRole("link", { name: /Printings/ })).not.toHaveAttribute(
      "aria-current",
    );
  });

  it("shows counts, including zero", () => {
    render(<UnderlineTabs label="Card views" items={items} />);
    // jsdom applies no CSS, so the flex-item count joins the name unspaced.
    expect(
      screen.getByRole("link", { name: /^Printings\s*12$/ }),
    ).toBeInTheDocument();
    expect(screen.getByText("0")).toHaveClass("tab-count");
    expect(screen.getByRole("link", { name: "Overview" }).textContent).toBe(
      "Overview",
    );
  });

  it("takes disabled tabs out of the tab order", () => {
    render(<UnderlineTabs label="Card views" items={items} />);
    const decks = screen.getByRole("link", { name: /Decks/ });
    expect(decks).toHaveAttribute("aria-disabled", "true");
    expect(decks).toHaveAttribute("tabindex", "-1");
    const printings = screen.getByRole("link", { name: /Printings/ });
    expect(printings).not.toHaveAttribute("aria-disabled");
    expect(printings).not.toHaveAttribute("tabindex");
  });
});
