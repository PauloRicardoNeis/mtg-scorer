import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { useState } from "react";
import { describe, expect, it, vi } from "vitest";
import { Checkbox, Chip, Radio, Segmented, Switch } from "./forms";

describe("Checkbox", () => {
  it("is a native checkbox named by its label", async () => {
    const user = userEvent.setup();
    const onChange = vi.fn();
    render(<Checkbox label="Include foils" name="foil" onChange={onChange} />);
    const box = screen.getByRole("checkbox", { name: "Include foils" });
    expect(box).toHaveClass("check");
    expect(box).toHaveAttribute("name", "foil");
    await user.click(screen.getByText("Include foils"));
    expect(box).toBeChecked();
    expect(onChange).toHaveBeenCalledTimes(1);
  });

  it("shows a partial selection and follows prop changes", () => {
    const { rerender } = render(<Checkbox label="All sets" indeterminate />);
    const box = screen.getByRole<HTMLInputElement>("checkbox", {
      name: "All sets",
    });
    expect(box.indeterminate).toBe(true);
    expect(box).toBePartiallyChecked();
    rerender(<Checkbox label="All sets" />);
    expect(box.indeterminate).toBe(false);
  });

  it("starts checked when asked", () => {
    render(<Checkbox label="Paper" defaultChecked />);
    expect(screen.getByRole("checkbox", { name: "Paper" })).toBeChecked();
  });
});

describe("Radio", () => {
  it("selects one of a group by name", async () => {
    const user = userEvent.setup();
    render(
      <>
        <Radio label="Paper" name="game" value="paper" defaultChecked />
        <Radio label="Arena" name="game" value="arena" />
      </>,
    );
    const paper = screen.getByRole("radio", { name: "Paper" });
    const arena = screen.getByRole("radio", { name: "Arena" });
    expect(paper).toHaveClass("radio");
    expect(paper).toBeChecked();
    await user.click(arena);
    expect(arena).toBeChecked();
    expect(paper).not.toBeChecked();
  });
});

describe("Switch", () => {
  it("is a checkbox exposed as a switch", async () => {
    const user = userEvent.setup();
    render(<Switch label="Show prices" />);
    const toggle = screen.getByRole("switch", { name: "Show prices" });
    expect(toggle).toHaveAttribute("type", "checkbox");
    expect(toggle).toHaveClass("switch", { exact: true });
    expect(toggle).not.toBeChecked();
    toggle.focus();
    await user.keyboard(" ");
    expect(toggle).toBeChecked();
  });

  it("has a compact variant", () => {
    render(<Switch label="Dense rows" compact />);
    expect(screen.getByRole("switch", { name: "Dense rows" })).toHaveClass(
      "switch",
      "compact",
    );
  });
});

describe("Chip", () => {
  it("is a checkbox inside a chip label", async () => {
    const user = userEvent.setup();
    render(<Chip label="Rare" name="rarity" value="rare" />);
    const chip = screen.getByRole("checkbox", { name: "Rare" });
    expect(chip.closest("label")).toHaveClass("chip");
    await user.click(chip);
    expect(chip).toBeChecked();
  });
});

describe("Segmented", () => {
  const options = [
    { value: "grid", label: "Grid" },
    { value: "list", label: "List" },
    { value: "table", label: "Table", disabled: true },
  ];

  it("groups the options under the legend", () => {
    render(<Segmented legend="View" name="view" options={options} />);
    expect(screen.getByRole("group", { name: "View" })).toHaveClass(
      "segmented",
      { exact: true },
    );
    expect(screen.getAllByRole("radio")).toHaveLength(3);
    expect(screen.getByRole("radio", { name: "Table" })).toBeDisabled();
  });

  it("starts from the default value and lets the user switch", async () => {
    const user = userEvent.setup();
    render(
      <Segmented
        legend="View"
        name="view"
        options={options}
        defaultValue="list"
      />,
    );
    expect(screen.getByRole("radio", { name: "List" })).toBeChecked();
    await user.click(screen.getByRole("radio", { name: "Grid" }));
    expect(screen.getByRole("radio", { name: "Grid" })).toBeChecked();
    expect(screen.getByRole("radio", { name: "List" })).not.toBeChecked();
  });

  it("does not select a disabled option", async () => {
    const user = userEvent.setup();
    render(
      <Segmented
        legend="View"
        name="view"
        options={options}
        defaultValue="grid"
      />,
    );
    await user.click(screen.getByRole("radio", { name: "Table" }));
    expect(screen.getByRole("radio", { name: "Table" })).not.toBeChecked();
    expect(screen.getByRole("radio", { name: "Grid" })).toBeChecked();
  });

  it("reports the chosen value when controlled", async () => {
    const user = userEvent.setup();
    const onChange = vi.fn();
    function Controlled() {
      const [value, setValue] = useState("grid");
      return (
        <Segmented
          legend="View"
          name="view"
          options={options}
          value={value}
          onChange={(next) => {
            onChange(next);
            setValue(next);
          }}
        />
      );
    }
    render(<Controlled />);
    expect(screen.getByRole("radio", { name: "Grid" })).toBeChecked();
    await user.click(screen.getByRole("radio", { name: "List" }));
    expect(onChange).toHaveBeenCalledWith("list");
    expect(screen.getByRole("radio", { name: "List" })).toBeChecked();
  });

  it("keeps the controlled value until the owner changes it", async () => {
    const user = userEvent.setup();
    const onChange = vi.fn();
    render(
      <Segmented
        legend="View"
        name="view"
        options={options}
        value="grid"
        onChange={onChange}
      />,
    );
    await user.click(screen.getByRole("radio", { name: "List" }));
    expect(onChange).toHaveBeenCalledWith("list");
    expect(screen.getByRole("radio", { name: "Grid" })).toBeChecked();
    expect(screen.getByRole("radio", { name: "List" })).not.toBeChecked();
  });

  it("can be disabled as a whole and sized small", () => {
    render(
      <Segmented
        legend="View"
        name="view"
        options={options}
        size="sm"
        disabled
      />,
    );
    expect(screen.getByRole("group", { name: "View" })).toHaveClass(
      "segmented",
      "sm",
    );
    for (const radio of screen.getAllByRole("radio"))
      expect(radio).toBeDisabled();
  });
});
