import { fireEvent, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";
import { Tooltip } from "./tooltip";

function tip(): HTMLElement {
  return screen.getByRole("tooltip", { hidden: true });
}

describe("Tooltip", () => {
  it("defaults to an info trigger named by its label and described by the tip", () => {
    render(
      <Tooltip label="About win rate">Games won over games played.</Tooltip>,
    );
    const trigger = screen.getByRole("button", { name: "About win rate" });
    expect(trigger).toHaveClass("info-trigger");
    expect(trigger).toHaveAttribute("type", "button");
    expect(trigger).toHaveAccessibleDescription("Games won over games played.");
    expect(trigger).toHaveAttribute("aria-describedby", tip().id);
    expect(trigger).not.toHaveAttribute("data-open");
    expect(tip()).not.toBeVisible();
  });

  it("uses custom trigger content as the button's name", () => {
    render(<Tooltip trigger="Methodology">How scores are built.</Tooltip>);
    const trigger = screen.getByRole("button", { name: "Methodology" });
    expect(trigger).toHaveClass("button", "ghost", "sm");
    expect(trigger).not.toHaveAttribute("aria-label");
  });

  it("opens on hover and closes when the pointer leaves", async () => {
    const user = userEvent.setup();
    render(
      <Tooltip label="About lift">Top-cut share over field share.</Tooltip>,
    );
    const trigger = screen.getByRole("button", { name: "About lift" });
    await user.hover(trigger);
    expect(screen.getByRole("tooltip")).toHaveTextContent(
      "Top-cut share over field share.",
    );
    expect(trigger).toHaveAttribute("data-open", "true");
    await user.unhover(trigger);
    expect(tip()).not.toBeVisible();
    expect(trigger).not.toHaveAttribute("data-open");
  });

  it("ignores touch hover so a tap can toggle it", () => {
    render(<Tooltip label="About lift">Top-cut share.</Tooltip>);
    const anchor = screen.getByRole("button").parentElement!;
    fireEvent.pointerEnter(anchor, { pointerType: "touch" });
    expect(tip()).not.toBeVisible();
    fireEvent.pointerEnter(anchor, { pointerType: "mouse" });
    expect(tip()).toBeVisible();
  });

  it("opens on keyboard focus and closes on blur", async () => {
    const user = userEvent.setup();
    render(
      <>
        <Tooltip label="About lift">Top-cut share.</Tooltip>
        <button type="button">Next</button>
      </>,
    );
    await user.tab();
    expect(screen.getByRole("button", { name: "About lift" })).toHaveFocus();
    expect(tip()).toBeVisible();
    await user.tab();
    expect(tip()).not.toBeVisible();
  });

  it("closes with Escape and reopens on the next focus", async () => {
    const user = userEvent.setup();
    render(
      <>
        <Tooltip label="About lift">Top-cut share.</Tooltip>
        <button type="button">Next</button>
      </>,
    );
    await user.tab();
    expect(tip()).toBeVisible();
    await user.keyboard("{Escape}");
    expect(tip()).not.toBeVisible();
    await user.tab();
    await user.tab({ shift: true });
    expect(tip()).toBeVisible();
  });

  it("reopens after Escape when hovered again", async () => {
    const user = userEvent.setup();
    render(<Tooltip label="About lift">Top-cut share.</Tooltip>);
    const trigger = screen.getByRole("button", { name: "About lift" });
    await user.hover(trigger);
    await user.keyboard("{Escape}");
    expect(tip()).not.toBeVisible();
    await user.unhover(trigger);
    await user.hover(trigger);
    expect(tip()).toBeVisible();
  });

  it("ignores keys other than Escape", async () => {
    const user = userEvent.setup();
    render(<Tooltip label="About lift">Top-cut share.</Tooltip>);
    await user.tab();
    await user.keyboard("{Enter}{ArrowDown}a");
    expect(tip()).toBeVisible();
  });

  it("toggles a pinned tip on click until focus leaves", () => {
    render(
      <>
        <Tooltip label="About lift">Top-cut share.</Tooltip>
        <button type="button">Next</button>
      </>,
    );
    const trigger = screen.getByRole("button", { name: "About lift" });
    // A tap on a touch screen: no hover, and the browser may not move focus.
    fireEvent.click(trigger);
    expect(tip()).toBeVisible();
    fireEvent.click(trigger);
    expect(tip()).not.toBeVisible();
    fireEvent.click(trigger);
    expect(tip()).toBeVisible();
    fireEvent.blur(trigger);
    expect(tip()).not.toBeVisible();
  });

  it("reopens a dismissed tip on click", async () => {
    const user = userEvent.setup();
    render(<Tooltip label="About lift">Top-cut share.</Tooltip>);
    const trigger = screen.getByRole("button", { name: "About lift" });
    fireEvent.click(trigger);
    await user.keyboard("{Escape}");
    expect(tip()).not.toBeVisible();
    fireEvent.click(trigger);
    fireEvent.click(trigger);
    expect(tip()).toBeVisible();
  });

  it("shows an optional eyebrow and title above the body", () => {
    render(
      <Tooltip label="About grade" eyebrow="Score" title="Letter grade">
        From A+ to F.
      </Tooltip>,
    );
    expect(tip().querySelector(".tooltip-eyebrow")).toHaveTextContent("Score");
    expect(tip().querySelector(".tooltip-title")).toHaveTextContent(
      "Letter grade",
    );
    expect(tip().querySelector(".tooltip-body")).toHaveTextContent(
      "From A+ to F.",
    );
  });

  it("omits the head without an eyebrow or title", () => {
    render(<Tooltip label="About grade">From A+ to F.</Tooltip>);
    expect(tip().querySelector(".tooltip-head")).toBeNull();
  });

  it("places the tip below and end-aligned when asked", () => {
    const { rerender } = render(
      <Tooltip label="About grade">From A+ to F.</Tooltip>,
    );
    expect(tip()).toHaveClass("tooltip", { exact: true });
    rerender(
      <Tooltip label="About grade" placement="below" align="end">
        From A+ to F.
      </Tooltip>,
    );
    expect(tip()).toHaveClass("tooltip", "below", "end");
  });

  it("gives each tooltip its own id", () => {
    render(
      <>
        <Tooltip label="First">One.</Tooltip>
        <Tooltip label="Second">Two.</Tooltip>
      </>,
    );
    expect(
      screen.getByRole("button", { name: "First" }),
    ).toHaveAccessibleDescription("One.");
    expect(
      screen.getByRole("button", { name: "Second" }),
    ).toHaveAccessibleDescription("Two.");
  });
});
