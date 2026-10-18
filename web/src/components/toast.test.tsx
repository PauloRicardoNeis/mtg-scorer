import { act, fireEvent, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { Toasts, type ToastMessage } from "./toast";

const saved: ToastMessage = {
  tone: "success",
  title: "Search URL copied.",
  message: "It stays pinned to this dataset.",
};

describe("Toasts", () => {
  it("keeps an empty status region mounted for announcements", () => {
    render(<Toasts toast={null} onDismiss={vi.fn()} />);
    const region = screen.getByRole("status");
    expect(region).toHaveClass("toast-region");
    expect(region).toBeEmptyDOMElement();
  });

  it("shows the toast's title, message and tone inside the region", () => {
    render(<Toasts toast={saved} onDismiss={vi.fn()} />);
    const region = screen.getByRole("status");
    expect(region).toHaveTextContent("Search URL copied.");
    expect(region).toHaveTextContent("It stays pinned to this dataset.");
    expect(region.firstElementChild).toHaveClass("toast", "success");
  });

  it("defaults to the accent tone and omits a missing message or action", () => {
    const { container } = render(
      <Toasts toast={{ title: "Saved." }} onDismiss={vi.fn()} />,
    );
    expect(container.querySelector(".toast")).toHaveClass("toast accent", {
      exact: true,
    });
    expect(container.querySelector(".toast-message")).toBeNull();
    expect(screen.getAllByRole("button")).toEqual([
      screen.getByRole("button", { name: "Dismiss" }),
    ]);
  });

  it("runs the toast's action", async () => {
    const user = userEvent.setup();
    const onClick = vi.fn();
    render(
      <Toasts
        toast={{ title: "Filter removed.", action: { label: "Undo", onClick } }}
        onDismiss={vi.fn()}
      />,
    );
    await user.click(screen.getByRole("button", { name: "Undo" }));
    expect(onClick).toHaveBeenCalledTimes(1);
  });

  it("dismisses from its close button", async () => {
    const user = userEvent.setup();
    const onDismiss = vi.fn();
    render(<Toasts toast={saved} onDismiss={onDismiss} />);
    await user.click(screen.getByRole("button", { name: "Dismiss" }));
    expect(onDismiss).toHaveBeenCalledTimes(1);
  });
});

// user-event waits on real timeouts between steps, so these drive the toast
// with synchronous events while the clock is fake.
describe("Toasts auto-dismiss", () => {
  beforeEach(() => {
    vi.useFakeTimers();
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  function advance(ms: number) {
    act(() => {
      vi.advanceTimersByTime(ms);
    });
  }

  function card(): HTMLElement {
    return screen.getByRole("status").querySelector<HTMLElement>(".toast")!;
  }

  it("closes the toast after four seconds", () => {
    const onDismiss = vi.fn();
    render(<Toasts toast={saved} onDismiss={onDismiss} />);
    advance(3999);
    expect(onDismiss).not.toHaveBeenCalled();
    advance(1);
    expect(onDismiss).toHaveBeenCalledTimes(1);
  });

  it("holds the toast open while the pointer is over it", () => {
    const onDismiss = vi.fn();
    render(<Toasts toast={saved} onDismiss={onDismiss} />);
    advance(2000);
    fireEvent.pointerEnter(card());
    advance(10_000);
    expect(onDismiss).not.toHaveBeenCalled();
    fireEvent.pointerLeave(card());
    advance(3999);
    expect(onDismiss).not.toHaveBeenCalled();
    advance(1);
    expect(onDismiss).toHaveBeenCalledTimes(1);
  });

  it("holds the toast open while keyboard focus is inside it", () => {
    const onDismiss = vi.fn();
    render(
      <>
        <Toasts toast={saved} onDismiss={onDismiss} />
        <button type="button">Elsewhere</button>
      </>,
    );
    act(() => screen.getByRole("button", { name: "Dismiss" }).focus());
    advance(10_000);
    expect(onDismiss).not.toHaveBeenCalled();
    act(() => screen.getByRole("button", { name: "Elsewhere" }).focus());
    advance(4000);
    expect(onDismiss).toHaveBeenCalledTimes(1);
  });

  it("restarts the timer for a new toast", () => {
    const onDismiss = vi.fn();
    const { rerender } = render(<Toasts toast={saved} onDismiss={onDismiss} />);
    advance(3000);
    rerender(
      <Toasts toast={{ title: "Copied again." }} onDismiss={onDismiss} />,
    );
    expect(screen.getByRole("status")).toHaveTextContent("Copied again.");
    advance(3000);
    expect(onDismiss).not.toHaveBeenCalled();
    advance(1000);
    expect(onDismiss).toHaveBeenCalledTimes(1);
  });

  it("keeps the timer but calls the latest handler when only it changes", () => {
    const first = vi.fn();
    const latest = vi.fn();
    const { rerender } = render(<Toasts toast={saved} onDismiss={first} />);
    advance(3000);
    rerender(<Toasts toast={saved} onDismiss={latest} />);
    advance(1000);
    expect(first).not.toHaveBeenCalled();
    expect(latest).toHaveBeenCalledTimes(1);
  });

  it("stops the timer once the toast is gone", () => {
    const onDismiss = vi.fn();
    const { rerender } = render(<Toasts toast={saved} onDismiss={onDismiss} />);
    rerender(<Toasts toast={null} onDismiss={onDismiss} />);
    expect(screen.getByRole("status")).toBeEmptyDOMElement();
    advance(10_000);
    expect(onDismiss).not.toHaveBeenCalled();
  });
});
