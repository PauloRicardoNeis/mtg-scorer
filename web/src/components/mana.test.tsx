import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";
import { ColorDots, ColorFilter, ManaCost, Rarity } from "./mana";

function pips(container: HTMLElement) {
  return [
    ...container.querySelectorAll(".pips > .pip, .pips > .pip-split"),
  ].map((pip) => ({ className: pip.className, text: pip.textContent }));
}

describe("ManaCost", () => {
  it("keeps the source text for assistive tech and hides the pips", () => {
    const { container } = render(<ManaCost cost="{2}{W}{U}" />);
    expect(screen.getByText("{2}{W}{U}")).toHaveClass("sr-only");
    expect(container.querySelector(".pips")).toHaveAttribute(
      "aria-hidden",
      "true",
    );
    expect(container.firstElementChild).toHaveClass(
      "mana-cost",
      "mana-cost-sm",
    );
  });

  it("draws one pip per symbol, colored by mana type", () => {
    const { container } = render(<ManaCost cost="{X}{2}{W}{U}{B}{R}{G}{C}" />);
    expect(pips(container)).toEqual([
      { className: "pip pip-generic", text: "X" },
      { className: "pip pip-generic", text: "2" },
      { className: "pip pip-w", text: "W" },
      { className: "pip pip-u", text: "U" },
      { className: "pip pip-b", text: "B" },
      { className: "pip pip-r", text: "R" },
      { className: "pip pip-g", text: "G" },
      { className: "pip pip-c", text: "C" },
    ]);
  });

  it("reads symbols case-insensitively", () => {
    const { container } = render(<ManaCost cost="{1}{r}" />);
    expect(pips(container)).toEqual([
      { className: "pip pip-generic", text: "1" },
      { className: "pip pip-r", text: "R" },
    ]);
  });

  it("splits hybrid pips between both halves", () => {
    const { container } = render(<ManaCost cost="{W/U}{2/B}" />);
    const [colored, generic] =
      container.querySelectorAll<HTMLElement>(".pip-hybrid");
    expect(colored.style.getPropertyValue("--pip-a")).toBe("var(--mana-w)");
    expect(colored.style.getPropertyValue("--pip-b")).toBe("var(--mana-u)");
    expect(colored).toBeEmptyDOMElement();
    expect(generic.style.getPropertyValue("--pip-a")).toBe("transparent");
    expect(generic.style.getPropertyValue("--pip-b")).toBe("var(--mana-b)");
  });

  it("marks Phyrexian mana with a P in its color", () => {
    const { container } = render(<ManaCost cost="{G/P}{2}" />);
    expect(pips(container)).toEqual([
      { className: "pip pip-g", text: "P" },
      { className: "pip pip-generic", text: "2" },
    ]);
  });

  it("separates the halves of split cards", () => {
    const { container } = render(<ManaCost cost="{1}{U} // {3}{R}" />);
    expect(pips(container).map(({ text }) => text)).toEqual([
      "1",
      "U",
      "//",
      "3",
      "R",
    ]);
    expect(screen.getByText("{1}{U} // {3}{R}")).toHaveClass("sr-only");
  });

  it("keeps a half without symbols as an empty side of the split", () => {
    const { container } = render(<ManaCost cost=" // {R}" />);
    expect(pips(container).map(({ text }) => text)).toEqual(["//", "R"]);
  });

  it("uses the large size when asked", () => {
    const { container } = render(<ManaCost cost="{W}" size="lg" />);
    expect(container.firstElementChild).toHaveClass("mana-cost-lg");
  });

  it("shows text without symbols as plain text", () => {
    const { container } = render(<ManaCost cost="No cost" />);
    expect(container.innerHTML).toBe("No cost");
  });

  it("renders nothing visible for an empty cost", () => {
    const { container } = render(<ManaCost cost="" />);
    expect(container).toBeEmptyDOMElement();
  });

  it("ignores empty braces", () => {
    const { container } = render(<ManaCost cost="{}" />);
    expect(container.innerHTML).toBe("{}");
  });
});

describe("ColorDots", () => {
  it("renders nothing for an unknown identity", () => {
    const { container } = render(<ColorDots values={null} />);
    expect(container).toBeEmptyDOMElement();
  });

  it("shows a colorless dot for an empty identity", () => {
    const { container } = render(<ColorDots values={[]} />);
    const dots = container.querySelectorAll(".color-dot");
    expect(dots).toHaveLength(1);
    expect(dots[0]).toHaveClass("pip-c");
  });

  it("shows one hidden dot per color, generic for unknown symbols", () => {
    const { container } = render(<ColorDots values={["W", "G", "P"]} />);
    expect(container.firstElementChild).toHaveAttribute("aria-hidden", "true");
    expect(
      [...container.querySelectorAll(".color-dot")].map((dot) => dot.className),
    ).toEqual(["color-dot pip-w", "color-dot pip-g", "color-dot pip-generic"]);
  });
});

describe("ColorFilter", () => {
  it("groups one named checkbox per color under its label", () => {
    render(<ColorFilter label="Colors" name="color" selected={[]} />);
    const group = screen.getByRole("group", { name: "Colors" });
    expect(group).toBeInTheDocument();
    expect(
      screen.getAllByRole("checkbox").map((box) => box.getAttribute("value")),
    ).toEqual(["W", "U", "B", "R", "G", "C"]);
    for (const name of ["White", "Blue", "Black", "Red", "Green", "Colorless"])
      expect(screen.getByRole("checkbox", { name })).toHaveAttribute(
        "name",
        "color",
      );
  });

  it("checks the selected colors", () => {
    render(<ColorFilter label="Colors" name="color" selected={["U", "C"]} />);
    expect(screen.getByRole("checkbox", { name: "Blue" })).toBeChecked();
    expect(screen.getByRole("checkbox", { name: "Colorless" })).toBeChecked();
    expect(screen.getByRole("checkbox", { name: "White" })).not.toBeChecked();
  });

  it("joins an outside form through the form attribute", () => {
    render(
      <ColorFilter label="Colors" name="color" selected={[]} form="filters" />,
    );
    for (const box of screen.getAllByRole("checkbox"))
      expect(box).toHaveAttribute("form", "filters");
  });

  it("toggles with the keyboard", async () => {
    const user = userEvent.setup();
    render(<ColorFilter label="Colors" name="color" selected={[]} />);
    await user.tab();
    expect(screen.getByRole("checkbox", { name: "White" })).toHaveFocus();
    await user.keyboard(" ");
    expect(screen.getByRole("checkbox", { name: "White" })).toBeChecked();
  });

  it("tints each dot with its mana color and titles the label", () => {
    const { container } = render(
      <ColorFilter label="Colors" name="color" selected={[]} />,
    );
    const dot = container.querySelector<HTMLElement>('[data-color="R"]');
    expect(dot?.style.getPropertyValue("--dot")).toBe("var(--mana-r)");
    expect(dot?.closest("label")).toHaveAttribute("title", "Red");
  });
});

describe("Rarity", () => {
  it.each(["common", "uncommon", "rare", "mythic"])(
    "shows a %s gem beside the name",
    (rarity) => {
      const { container } = render(<Rarity rarity={rarity} />);
      expect(container.firstElementChild).toHaveTextContent(rarity);
      expect(container.querySelector(".gem")).toHaveClass(`gem-${rarity}`);
      expect(container.querySelector(".gem")).toHaveAttribute(
        "aria-hidden",
        "true",
      );
    },
  );

  it("falls back to the common gem for other rarities", () => {
    const { container } = render(<Rarity rarity="special" />);
    expect(container.firstElementChild).toHaveTextContent("special");
    expect(container.querySelector(".gem")).toHaveClass("gem gem-common", {
      exact: true,
    });
  });
});
