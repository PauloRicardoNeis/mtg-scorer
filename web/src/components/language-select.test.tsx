import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import { I18nProvider } from "@/i18n/context";
import { setLocale } from "@/i18n/actions";
import { de } from "@/i18n/messages/de";
import { LanguageSelect } from "./language-select";

vi.mock("@/i18n/actions", () => ({ setLocale: vi.fn() }));

describe("LanguageSelect", () => {
  it("names every language in its own language", () => {
    render(<LanguageSelect />);
    const select = screen.getByRole("combobox", { name: "Language" });
    expect(select).toHaveValue("en");
    const options = screen.getAllByRole("option");
    expect(options.map((option) => option.textContent)).toEqual([
      "English",
      "Español",
      "Français",
      "Deutsch",
      "Italiano",
      "Português (Brasil)",
      "日本語",
      "한국어",
      "Русский",
      "简体中文",
      "繁體中文",
    ]);
    expect(screen.getByRole("option", { name: "日本語" })).toHaveAttribute(
      "lang",
      "ja",
    );
  });

  it("shows the reader's current language in it", () => {
    render(
      <I18nProvider locale="de" messages={de}>
        <LanguageSelect />
      </I18nProvider>,
    );
    expect(
      screen.getByRole("combobox", { name: de.language.label }),
    ).toHaveValue("de");
  });

  it("saves a new choice as soon as it is picked", async () => {
    render(<LanguageSelect />);
    await userEvent.selectOptions(
      screen.getByRole("combobox", { name: "Language" }),
      "pt-BR",
    );
    await waitFor(() => expect(setLocale).toHaveBeenCalledOnce());
    const form = vi.mocked(setLocale).mock.calls[0][0];
    expect(form.get("locale")).toBe("pt-BR");
  });
});
