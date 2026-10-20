import { test, expect } from "@playwright/test";
import AxeBuilder from "@axe-core/playwright";

// verify publishes one SYNTHETIC Modern run, so Modern is the one comparable format.
const results = (page: import("@playwright/test").Page) =>
  page
    .getByRole("region", { name: "Cards across formats" })
    .getByRole("status");

test("the All formats tab compares cards by grade and keeps choices in the address", async ({
  page,
}) => {
  await page.goto("/rankings");
  await page
    .getByRole("navigation", { name: "Formats" })
    .getByRole("link", { name: /All formats/ })
    .click();
  await expect(page).toHaveURL(/\/rankings\/compare$/);
  await expect(
    page.getByRole("heading", { level: 1, name: "Across formats" }),
  ).toBeVisible();
  await expect(
    page
      .getByRole("navigation", { name: "Presets" })
      .getByRole("link", { name: "Grades" }),
  ).toHaveAttribute("aria-current", "page");
  await expect(page.getByRole("checkbox", { name: "Modern" })).toBeChecked();

  // Publication checks leave other formats active, so pin Modern for exact counts.
  await page.goto(
    "/rankings/compare?picked=1&format=Modern&stat=grade&summary=best&summary=count",
  );
  await expect(results(page)).toHaveText(
    /^1–8 of 8 cards · 1 format · 3 columns$/,
  );

  const table = page.getByRole("table");
  await expect(
    table.getByRole("row", { name: /Lightning Bolt/ }),
  ).toContainText("Modern");
  await expect(table.getByRole("row").nth(2)).toContainText("Lightning Bolt");

  await page.getByRole("checkbox", { name: "Meta share" }).click();
  await expect(page).toHaveURL(/stat=share/);
  await expect(page.getByText("Custom", { exact: true })).toBeVisible();
  await expect(results(page)).toHaveText(/4 columns$/);

  await table.getByRole("link", { name: "Card" }).click();
  await expect(page).toHaveURL(/sort=name/);
  await expect(table.getByRole("row").nth(2)).toContainText(
    "Bonecrusher Giant",
  );
  expect((await new AxeBuilder({ page }).analyze()).violations).toEqual([]);
});

test("the last format stays on and an every-format filter can empty the table", async ({
  page,
}) => {
  await page.goto(
    "/rankings/compare?picked=1&format=Modern&stat=grade&q=nothing-matches",
  );
  await expect(
    page.getByRole("heading", { level: 3, name: "No cards match." }),
  ).toBeVisible();
  const modern = page.getByRole("checkbox", { name: "Modern" });
  await modern.click();
  await expect(modern).toBeChecked();
  await page.getByRole("link", { name: "Deep dive" }).click();
  await expect(page).toHaveURL(/stat=trend/);
  await expect(page.getByRole("checkbox", { name: "Trend" })).toBeChecked();
});
