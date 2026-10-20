import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";
import {
  ColorFilter,
  ColorPips,
  ManaCost,
  Rarity,
  SymbolText,
  symbolSrc,
} from "./mana";

const base = "https://svgs.scryfall.io/card-symbols/";

function pips(container: HTMLElement) {
  return [
    ...container.querySelectorAll(".pips > .pip, .pips > .pip-split"),
  ].map((pip) =>
    pip.tagName === "IMG"
      ? pip.getAttribute("src")!.replace(base, "")
      : pip.textContent,
  );
}

describe("symbolSrc", () => {
  it.each([
    ["W", "W.svg"],
    ["2", "2.svg"],
    ["20", "20.svg"],
    ["T", "T.svg"],
    ["W/U", "WU.svg"],
    ["2/B", "2B.svg"],
    ["G/P", "GP.svg"],
    ["W/U/P", "WUP.svg"],
    ["C/R", "CR.svg"],
    ["½", "HALF.svg"],
    ["∞", "INFINITY.svg"],
  ])("draws {%s} from Scryfall's %s", (symbol, file) => {
    expect(symbolSrc(symbol)).toBe(base + file);
  });

  it.each(["21", "W/X", "w", "FOO", ""])(
    "has no drawing for {%s}",
    (symbol) => {
      expect(symbolSrc(symbol)).toBeNull();
    },
  );
});

describe("ManaCost", () => {
  it("keeps the source text for assistive tech and hides the symbols", () => {
    const { container } = render(<ManaCost cost="{2}{W}{U}" />);
    expect(screen.getByText("{2}{W}{U}")).toHaveClass("sr-only");
    expect(container.querySelector(".pips")).toHaveAttribute(
      "aria-hidden",
      "true",
    );
    for (const pip of container.querySelectorAll(".pip"))
      expect(pip).toHaveAttribute("alt", "");
    expect(container.firstElementChild).toHaveClass(
      "mana-cost",
      "mana-cost-sm",
    );
  });

  it("draws one official symbol per mana symbol", () => {
    const { container } = render(<ManaCost cost="{X}{2}{W}{U}{B}{R}{G}{C}" />);
    expect(pips(container)).toEqual(
      ["X", "2", "W", "U", "B", "R", "G", "C"].map((s) => `${s}.svg`),
    );
  });

  it("reads symbols case-insensitively", () => {
    const { container } = render(<ManaCost cost="{1}{r}" />);
    expect(pips(container)).toEqual(["1.svg", "R.svg"]);
  });

  it("draws hybrid and Phyrexian symbols", () => {
    const { container } = render(<ManaCost cost="{W/U}{2/B}{G/P}{R/W/P}" />);
    expect(pips(container)).toEqual(["WU.svg", "2B.svg", "GP.svg", "RWP.svg"]);
  });

  it("keeps a symbol Scryfall does not draw as text", () => {
    const { container } = render(<ManaCost cost="{25}{W}" />);
    expect(pips(container)).toEqual(["25", "W.svg"]);
    expect(container.querySelector(".pip-text")).toHaveTextContent("25");
  });

  it("separates the halves of split cards", () => {
    const { container } = render(<ManaCost cost="{1}{U} // {3}{R}" />);
    expect(pips(container)).toEqual(["1.svg", "U.svg", "//", "3.svg", "R.svg"]);
    expect(screen.getByText("{1}{U} // {3}{R}")).toHaveClass("sr-only");
  });

  it("keeps a half without symbols as an empty side of the split", () => {
    const { container } = render(<ManaCost cost=" // {R}" />);
    expect(pips(container)).toEqual(["//", "R.svg"]);
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

describe("SymbolText", () => {
  it("draws symbols inline and keeps their text for assistive tech", () => {
    const { container } = render(
      <p>
        <SymbolText text={"{T}: Add {G}.\n{2/G}, {Q}: Draw a card."} />
      </p>,
    );
    expect(container).toHaveTextContent(
      "{T}: Add {G}. {2/G}, {Q}: Draw a card.",
    );
    expect(
      [...container.querySelectorAll(".inline-symbol img")].map((img) =>
        img.getAttribute("src")!.replace(base, ""),
      ),
    ).toEqual(["T.svg", "G.svg", "2G.svg", "Q.svg"]);
    for (const symbol of container.querySelectorAll(".inline-symbol")) {
      expect(symbol.querySelector(".sr-only")?.textContent).toMatch(/^\{.+\}$/);
      expect(symbol.querySelector("img")).toHaveAttribute("alt", "");
    }
  });

  it("keeps text without symbols and unknown symbols as they are", () => {
    const { container } = render(
      <p>
        <SymbolText text="Flying. {FOO} stays {}" />
      </p>,
    );
    expect(container.innerHTML).toBe("<p>Flying. {FOO} stays {}</p>");
  });
});

describe("ColorPips", () => {
  it("renders nothing for an unknown identity", () => {
    const { container } = render(<ColorPips values={null} />);
    expect(container).toBeEmptyDOMElement();
  });

  it("shows the colorless symbol for an empty identity", () => {
    const { container } = render(<ColorPips values={[]} />);
    const shown = container.querySelectorAll(".pip");
    expect(shown).toHaveLength(1);
    expect(shown[0]).toHaveAttribute("src", `${base}C.svg`);
  });

  it("shows one hidden symbol per color, text for other values", () => {
    const { container } = render(<ColorPips values={["W", "G", "P"]} />);
    expect(container.firstElementChild).toHaveAttribute("aria-hidden", "true");
    const shown = [...container.querySelectorAll(".pip")];
    expect(shown.map((pip) => pip.getAttribute("src"))).toEqual([
      `${base}W.svg`,
      `${base}G.svg`,
      null,
    ]);
    expect(shown[2]).toHaveClass("pip-text");
    expect(shown[2]).toHaveTextContent("P");
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

  it("can keep its label for assistive tech only", () => {
    render(<ColorFilter label="Colors" name="color" selected={[]} hideLabel />);
    expect(screen.getByRole("group", { name: "Colors" })).toBeInTheDocument();
    expect(screen.getByText("Colors")).toHaveClass("sr-only");
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

  it("draws each color's symbol, glowing in its color, and titles the label", () => {
    const { container } = render(
      <ColorFilter label="Colors" name="color" selected={[]} />,
    );
    const symbol = container.querySelector<HTMLElement>('[data-color="R"]');
    expect(symbol).toHaveAttribute("src", `${base}R.svg`);
    expect(symbol).toHaveAttribute("alt", "");
    expect(symbol?.style.getPropertyValue("--glow")).toBe("var(--mana-r)");
    expect(symbol?.closest("label")).toHaveAttribute("title", "Red");
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

  it("names a rarity it has no word for as the source does", () => {
    const { container } = render(<Rarity rarity="timeshifted" />);
    expect(container.firstElementChild).toHaveTextContent("timeshifted");
  });

  it("falls back to the common gem for other rarities", () => {
    const { container } = render(<Rarity rarity="special" />);
    expect(container.firstElementChild).toHaveTextContent("special");
    expect(container.querySelector(".gem")).toHaveClass("gem gem-common", {
      exact: true,
    });
  });
});
