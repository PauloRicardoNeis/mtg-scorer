import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";
import { ApiError } from "@/lib/api";
import { router } from "@/test/navigation";
import { Problem } from "./problem";

describe("Problem", () => {
  it("explains an unavailable catalog", () => {
    render(<Problem error={new ApiError("catalog_unavailable", 503)} />);
    const alert = screen.getByRole("alert");
    expect(alert).toHaveTextContent("Dataset unavailable");
    expect(
      screen.getByRole("heading", {
        level: 1,
        name: "The catalog is taking a break.",
      }),
    ).toBeInTheDocument();
    expect(alert).toHaveTextContent("Your search URL is preserved");
  });

  it("explains a missing card or dataset", () => {
    render(<Problem error={new ApiError("card_not_found", 404)} />);
    expect(screen.getByRole("alert")).toHaveTextContent(
      "Unable to open this view",
    );
    expect(
      screen.getByRole("heading", {
        level: 1,
        name: "This request could not be completed.",
      }),
    ).toBeInTheDocument();
    expect(screen.getByRole("alert")).toHaveTextContent(
      "This card, dataset or score run could not be found.",
    );
  });

  it("explains a format without published rankings", () => {
    render(<Problem error={new ApiError("rankings_unavailable", 503)} />);
    expect(screen.getByRole("alert")).toHaveTextContent("Rankings unavailable");
    expect(
      screen.getByRole("heading", {
        level: 1,
        name: "No rankings are published for this format yet.",
      }),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("link", { name: "Back to rankings" }),
    ).toHaveAttribute("href", "/rankings");
    expect(screen.queryByRole("button", { name: "Retry" })).toBeNull();
  });

  it("points other failures back to the search", () => {
    render(<Problem error={new ApiError("invalid_query", 400)} />);
    expect(screen.getByRole("alert")).toHaveTextContent(
      "Check the search URL, or return to discovery to start a new search.",
    );
  });

  it("offers a retry and a way back to discovery", async () => {
    const user = userEvent.setup();
    render(<Problem error={new ApiError("internal_error", 500)} />);
    expect(
      screen.getByRole("link", { name: "Return to discovery" }),
    ).toHaveAttribute("href", "/cards");
    await user.click(screen.getByRole("button", { name: "Retry" }));
    expect(router.refresh).toHaveBeenCalledTimes(1);
  });
});
