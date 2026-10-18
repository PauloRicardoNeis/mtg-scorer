import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import { router } from "@/test/navigation";
import { CopySearch, Retry } from "./actions";

describe("CopySearch", () => {
  it("copies the page URL and confirms it", async () => {
    const user = userEvent.setup();
    window.history.pushState(
      null,
      "",
      "/cards?catalog_snapshot_id=snap-1&q=Æther",
    );
    render(<CopySearch />);
    expect(screen.getByRole("status")).toBeEmptyDOMElement();

    await user.click(
      screen.getByRole("button", { name: "Copy this search URL" }),
    );

    expect(location.search).toBe("?catalog_snapshot_id=snap-1&q=%C3%86ther");
    await expect(navigator.clipboard.readText()).resolves.toBe(location.href);
    const status = screen.getByRole("status");
    expect(status).toHaveTextContent("Search URL copied.");
    expect(status).toHaveTextContent("It stays pinned to this dataset.");
    expect(status.querySelector(".toast")).toHaveClass("success");
  });

  it("explains a copy the browser refused", async () => {
    const user = userEvent.setup();
    vi.spyOn(navigator.clipboard, "writeText").mockRejectedValue(
      new DOMException("Write permission denied.", "NotAllowedError"),
    );
    render(<CopySearch />);

    await user.click(
      screen.getByRole("button", { name: "Copy this search URL" }),
    );

    const status = screen.getByRole("status");
    expect(status).toHaveTextContent("Couldn't copy the URL.");
    expect(status).toHaveTextContent("Copy it from your browser address bar.");
    expect(status.querySelector(".toast")).toHaveClass("warning");
  });

  it("closes the confirmation from its dismiss button", async () => {
    const user = userEvent.setup();
    render(<CopySearch />);
    await user.click(
      screen.getByRole("button", { name: "Copy this search URL" }),
    );
    expect(screen.getByRole("status")).not.toBeEmptyDOMElement();

    await user.click(screen.getByRole("button", { name: "Dismiss" }));

    expect(screen.getByRole("status")).toBeEmptyDOMElement();
  });
});

describe("Retry", () => {
  it("refreshes the current route", async () => {
    const user = userEvent.setup();
    render(<Retry />);
    await user.click(screen.getByRole("button", { name: "Retry" }));
    expect(router.refresh).toHaveBeenCalledTimes(1);
    expect(router.push).not.toHaveBeenCalled();
  });
});
