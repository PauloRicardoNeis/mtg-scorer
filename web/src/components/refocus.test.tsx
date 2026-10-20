import { render, screen } from "@testing-library/react";
import { useRef } from "react";
import { describe, expect, it } from "vitest";
import { rememberFocus, useRefocus } from "./refocus";

function Toolbar({ address }: { address: string }) {
  const form = useRef<HTMLFormElement>(null);
  useRefocus(form, address);
  return (
    <form ref={form} aria-label="Toolbar">
      <select name="type" aria-label="Card type">
        <option value="">All</option>
      </select>
      <input type="checkbox" name="color" value="R" aria-label="Red" />
      <input type="checkbox" name="color" value="U" aria-label="Blue" />
    </form>
  );
}

describe("refocus", () => {
  it("hands focus back to the noted select after the toolbar remounts", () => {
    const { unmount } = render(<Toolbar address="a" />);
    rememberFocus(screen.getByRole("combobox", { name: "Card type" }));
    unmount();
    render(<Toolbar address="b" />);
    expect(screen.getByRole("combobox", { name: "Card type" })).toHaveFocus();
  });

  it("finds the exact checkbox among those sharing a name", () => {
    const { unmount } = render(<Toolbar address="a" />);
    rememberFocus(screen.getByRole("checkbox", { name: "Blue" }));
    unmount();
    render(<Toolbar address="b" />);
    expect(screen.getByRole("checkbox", { name: "Blue" })).toHaveFocus();
  });

  it("leaves focus that is already in the form, and forgets the note", () => {
    const { rerender, unmount } = render(<Toolbar address="a" />);
    screen.getByRole("checkbox", { name: "Red" }).focus();
    rememberFocus(screen.getByRole("combobox", { name: "Card type" }));
    rerender(<Toolbar address="b" />);
    expect(screen.getByRole("checkbox", { name: "Red" })).toHaveFocus();
    unmount();
    render(<Toolbar address="c" />);
    expect(document.body).toHaveFocus();
  });

  it("ignores changes that do not come from a form control", () => {
    rememberFocus(document.createElement("button"));
    rememberFocus(null);
    render(<Toolbar address="a" />);
    expect(document.body).toHaveFocus();
  });
});
