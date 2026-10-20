import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";
import { router, setPathname } from "@/test/navigation";
import { HeaderSearch } from "./header-search";

function searchBox(): HTMLInputElement {
  return screen.getByRole("searchbox", { name: "Search cards" });
}

/** The search the form navigated to, parsed. */
function pushed(): URL {
  expect(router.push).toHaveBeenCalledTimes(1);
  return new URL(String(router.push.mock.calls[0][0]), location.origin);
}

describe("HeaderSearch", () => {
  it("is a labelled search landmark advertising its shortcut", () => {
    render(<HeaderSearch />);
    expect(screen.getByRole("search")).toHaveAttribute("action", "/cards");
    const input = searchBox();
    expect(input).toHaveAttribute("aria-keyshortcuts", "/");
    expect(input).toHaveAttribute("maxlength", "100");
    expect(input).toHaveAttribute("autocomplete", "off");
  });

  describe("the / shortcut", () => {
    it("focuses the search and selects its text from anywhere on the page", async () => {
      const user = userEvent.setup();
      render(<HeaderSearch />);
      await user.type(searchBox(), "bolt");
      await user.click(document.body);
      expect(searchBox()).not.toHaveFocus();

      await user.keyboard("/");

      expect(searchBox()).toHaveFocus();
      expect(searchBox()).toHaveValue("bolt");
      expect(searchBox().selectionStart).toBe(0);
      expect(searchBox().selectionEnd).toBe(4);
    });

    it("focuses the search from a focused button", async () => {
      const user = userEvent.setup();
      render(
        <>
          <button type="button">Elsewhere</button>
          <HeaderSearch />
        </>,
      );
      await user.tab();
      expect(screen.getByRole("button", { name: "Elsewhere" })).toHaveFocus();
      await user.keyboard("/");
      expect(searchBox()).toHaveFocus();
      expect(searchBox()).toHaveValue("");
    });

    it.each([
      ["a text field", <input key="field" aria-label="Other" />],
      ["a text area", <textarea key="field" aria-label="Other" />],
    ])("types a slash into %s instead", async (_, field) => {
      const user = userEvent.setup();
      render(
        <>
          {field}
          <HeaderSearch />
        </>,
      );
      const other = screen.getByRole("textbox", { name: "Other" });
      await user.click(other);
      await user.keyboard("/");
      expect(other).toHaveFocus();
      expect(other).toHaveValue("/");
    });

    it("leaves a focused select alone", async () => {
      const user = userEvent.setup();
      render(
        <>
          <select aria-label="Other">
            <option>One</option>
          </select>
          <HeaderSearch />
        </>,
      );
      await user.tab();
      await user.keyboard("/");
      expect(screen.getByRole("combobox", { name: "Other" })).toHaveFocus();
    });

    it("leaves editable content alone", async () => {
      const user = userEvent.setup();
      render(
        <>
          <div contentEditable aria-label="Notes" tabIndex={0} />
          <HeaderSearch />
        </>,
      );
      const notes = screen.getByLabelText("Notes");
      // jsdom does not compute isContentEditable.
      Object.defineProperty(notes, "isContentEditable", { value: true });
      notes.focus();
      await user.keyboard("/");
      expect(notes).toHaveFocus();
    });

    it.each(["Control", "Meta", "Alt"])(
      "ignores / pressed with %s",
      async (modifier) => {
        const user = userEvent.setup();
        render(<HeaderSearch />);
        await user.keyboard(`{${modifier}>}/{/${modifier}}`);
        expect(searchBox()).not.toHaveFocus();
      },
    );

    it("ignores other keys", async () => {
      const user = userEvent.setup();
      render(<HeaderSearch />);
      await user.keyboard("s?");
      expect(searchBox()).not.toHaveFocus();
    });

    it("yields to a handler that already took the key", async () => {
      const user = userEvent.setup();
      render(
        <>
          <div
            role="application"
            aria-label="Board"
            tabIndex={0}
            onKeyDown={(event) => event.preventDefault()}
          />
          <HeaderSearch />
        </>,
      );
      await user.tab();
      await user.keyboard("/");
      expect(screen.getByRole("application", { name: "Board" })).toHaveFocus();
    });

    it("stops listening once unmounted", () => {
      const { unmount } = render(<HeaderSearch />);
      unmount();
      const event = new KeyboardEvent("keydown", {
        key: "/",
        bubbles: true,
        cancelable: true,
      });
      document.body.dispatchEvent(event);
      expect(event.defaultPrevented).toBe(false);
    });
  });

  describe("submitting", () => {
    it("searches the trimmed name within the dataset in the query", async () => {
      const user = userEvent.setup();
      window.history.pushState(
        null,
        "",
        "/cards?catalog_snapshot_id=snap-1&q=old&set=m11",
      );
      render(<HeaderSearch />);
      await user.type(searchBox(), "  Æther Vial  {Enter}");
      const url = pushed();
      expect(url.pathname).toBe("/cards");
      expect([...url.searchParams]).toEqual([
        ["catalog_snapshot_id", "snap-1"],
        ["q", "Æther Vial"],
      ]);
    });

    it("searches within the dataset named by a dataset page's path", async () => {
      const user = userEvent.setup();
      window.history.pushState(null, "", "/datasets/snap%202026/sets");
      render(<HeaderSearch />);
      await user.type(searchBox(), "bolt{Enter}");
      expect([...pushed().searchParams]).toEqual([
        ["catalog_snapshot_id", "snap 2026"],
        ["q", "bolt"],
      ]);
    });

    it("prefers the dataset in the query over the path", async () => {
      const user = userEvent.setup();
      window.history.pushState(
        null,
        "",
        "/datasets/from-path?catalog_snapshot_id=from-query",
      );
      render(<HeaderSearch />);
      await user.type(searchBox(), "bolt{Enter}");
      expect(pushed().searchParams.get("catalog_snapshot_id")).toBe(
        "from-query",
      );
    });

    it("opens discovery without filters from a blank search off a dataset", async () => {
      const user = userEvent.setup();
      window.history.pushState(null, "", "/datasets");
      render(<HeaderSearch />);
      await user.type(searchBox(), "   {Enter}");
      expect(router.push).toHaveBeenCalledExactlyOnceWith("/cards");
    });

    it("searches without a dataset when the dataset path is malformed", async () => {
      const user = userEvent.setup();
      window.history.pushState(null, "", "/datasets/%E0%A4%A/sets");
      render(<HeaderSearch />);
      await user.type(searchBox(), "bolt{Enter}");
      expect(router.push).toHaveBeenCalledExactlyOnceWith("/cards?q=bolt");
    });

    it("keeps the dataset for a blank search", async () => {
      const user = userEvent.setup();
      window.history.pushState(null, "", "/cards?catalog_snapshot_id=snap-1");
      render(<HeaderSearch />);
      await user.click(searchBox());
      await user.keyboard("{Enter}");
      expect([...pushed().searchParams]).toEqual([
        ["catalog_snapshot_id", "snap-1"],
      ]);
    });
  });

  describe("on rankings", () => {
    function rankedBox(): HTMLInputElement {
      return screen.getByRole("searchbox", { name: "Search ranked cards" });
    }

    function onRankings(search: string) {
      window.history.pushState(null, "", `/rankings${search}`);
      setPathname("/rankings");
    }

    it("searches the ranked cards instead of the catalog", () => {
      onRankings("");
      render(<HeaderSearch />);
      expect(screen.getByRole("search")).toHaveAttribute("action", "/rankings");
      expect(rankedBox()).toHaveAttribute("placeholder", "Search ranked cards");
    });

    it("shows the name filter in the address", () => {
      onRankings("?format=Modern&q=bolt");
      render(<HeaderSearch />);
      expect(rankedBox()).toHaveValue("bolt");
    });

    it("keeps the run and the other filters, replacing the name and the page", async () => {
      const user = userEvent.setup();
      onRankings(
        "?format=Modern&score_run_id=run-1&type=instant&color=R&q=old&offset=24",
      );
      render(<HeaderSearch />);
      await user.clear(rankedBox());
      await user.type(rankedBox(), "  Fire // Ice {Enter}");
      const url = pushed();
      expect(url.pathname).toBe("/rankings");
      expect([...url.searchParams]).toEqual([
        ["format", "Modern"],
        ["score_run_id", "run-1"],
        ["type", "instant"],
        ["color", "R"],
        ["q", "Fire // Ice"],
      ]);
    });

    it("drops the name filter for a blank search", async () => {
      const user = userEvent.setup();
      onRankings("?format=Modern&q=old");
      render(<HeaderSearch />);
      await user.clear(rankedBox());
      await user.keyboard("{Enter}");
      expect(router.push).toHaveBeenCalledExactlyOnceWith(
        "/rankings?format=Modern",
      );
    });

    it("opens the default rankings from a blank search without filters", async () => {
      const user = userEvent.setup();
      onRankings("");
      render(<HeaderSearch />);
      await user.type(rankedBox(), "{Enter}");
      expect(router.push).toHaveBeenCalledExactlyOnceWith("/rankings");
    });

    it("searches the compare table from the compare page", async () => {
      const user = userEvent.setup();
      window.history.pushState(
        null,
        "",
        "/rankings/compare?format=Modern&q=old",
      );
      setPathname("/rankings/compare");
      render(<HeaderSearch />);
      await user.clear(rankedBox());
      await user.type(rankedBox(), "bolt{Enter}");
      expect(router.push).toHaveBeenCalledExactlyOnceWith(
        "/rankings/compare?format=Modern&q=bolt",
      );
    });

    it("follows the name filter as the address changes, and clears it on leaving", () => {
      onRankings("?q=bolt");
      const { rerender } = render(<HeaderSearch />);
      window.history.pushState(null, "", "/rankings?q=ice");
      rerender(<HeaderSearch />);
      expect(rankedBox()).toHaveValue("ice");

      window.history.pushState(null, "", "/cards");
      setPathname("/cards");
      rerender(<HeaderSearch />);
      expect(searchBox()).toHaveValue("");
    });
  });
});
