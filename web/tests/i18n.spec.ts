import { test, expect, type Browser } from "@playwright/test";
import { de } from "../src/i18n/messages/de";
import { ja } from "../src/i18n/messages/ja";
import { ptBR } from "../src/i18n/messages/pt-BR";

// The site speaks the browser's language until the reader picks another, which a
// cookie keeps across pages; without JavaScript the picker's Apply button saves it.
async function visit(
  browser: Browser,
  options: { locale: string; javaScriptEnabled?: boolean },
) {
  const context = await browser.newContext(options);
  const page = await context.newPage();
  await page.goto("/cards");
  return { context, page };
}

test("opens in the browser's language", async ({ browser }) => {
  const { context, page } = await visit(browser, { locale: "de-DE" });
  await expect(page.locator("html")).toHaveAttribute("lang", "de");
  await expect(
    page.getByRole("navigation", { name: de.nav.main }).getByRole("link", {
      name: de.nav.discovery,
    }),
  ).toHaveAttribute("aria-current", "page");
  await expect(page.getByRole("heading", { level: 1 })).toContainText(
    de.cards.title,
  );
  await context.close();
});

test("falls back to English for a language it does not offer", async ({
  browser,
}) => {
  const { context, page } = await visit(browser, { locale: "nl-NL" });
  await expect(page.locator("html")).toHaveAttribute("lang", "en");
  await expect(page.getByRole("combobox", { name: "Language" })).toHaveValue(
    "en",
  );
  await context.close();
});

test("keeps a chosen language on every page", async ({ browser }) => {
  const { context, page } = await visit(browser, { locale: "en-US" });
  await page
    .getByRole("combobox", { name: "Language" })
    .selectOption({ label: "日本語" });
  await expect(page.locator("html")).toHaveAttribute("lang", "ja");
  await expect(
    page.getByRole("link", { name: ja.nav.methodology }),
  ).toBeVisible();
  await page.getByRole("link", { name: ja.nav.methodology }).click();
  await expect(page.getByText(ja.dataset.eyebrow)).toBeVisible();
  expect(
    (await context.cookies()).find((cookie) => cookie.name === "locale")?.value,
  ).toBe("ja");
  await context.close();
});

test("saves a language without JavaScript", async ({ browser }) => {
  const { context, page } = await visit(browser, {
    locale: "en-US",
    javaScriptEnabled: false,
  });
  await page.getByRole("combobox", { name: "Language" }).selectOption("pt-BR");
  await page.getByRole("button", { name: "Apply" }).click();
  await expect(page.locator("html")).toHaveAttribute("lang", "pt-BR");
  await expect(
    page.getByRole("link", { name: ptBR.nav.discovery }),
  ).toBeVisible();
  await context.close();
});
