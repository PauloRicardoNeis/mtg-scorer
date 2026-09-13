import { test, expect } from "@playwright/test";
import AxeBuilder from "@axe-core/playwright";
import { execFileSync } from "node:child_process";
import path from "node:path";

function control(action: string, ...args: string[]) {
  const python =
    process.env.CATALOG_TEST_PYTHON ??
    path.resolve(
      "../analytics/.venv",
      process.platform === "win32" ? "Scripts/python.exe" : "bin/python",
    );
  return execFileSync(
    python,
    [path.resolve("../scripts/e2e_control.py"), action, ...args],
    { encoding: "utf8" },
  );
}

test("guest filters, faces, source dataset, shareable URL and keyboard access", async ({
  page,
  context,
}) => {
  const outbound: string[] = [];
  page.on("request", (request) => {
    if (!new URL(request.url()).hostname.match(/^(127\.0\.0\.1|localhost)$/))
      outbound.push(request.url());
  });
  await page.goto("/cards");
  await expect(page).toHaveURL(/catalog_snapshot_id=catalog-/);
  await expect(
    page.getByRole("heading", { name: /Find something/ }),
  ).toBeVisible();
  await page.screenshot({
    path: "test-results/discovery-desktop.png",
    fullPage: true,
  });
  await page.keyboard.press("Tab");
  await expect(
    page.getByRole("link", { name: "Skip to content" }),
  ).toBeFocused();
  await page.getByLabel("Card or face name").fill("Insectile");
  await page.getByRole("button", { name: "Find cards", exact: true }).click();
  await expect(
    page.getByRole("link", {
      name: "Delver of Secrets // Insectile Aberration",
      exact: true,
    }),
  ).toBeVisible();
  await expect(page).toHaveURL(/q=Insectile/);
  const pinned = page.url();
  const snapshot = new URL(pinned).searchParams.get("catalog_snapshot_id")!;
  await context.grantPermissions(["clipboard-read", "clipboard-write"]);
  await page.getByRole("button", { name: "Copy this search URL" }).click();
  await expect(
    page.getByRole("status").filter({ hasText: "Search URL copied." }),
  ).toBeVisible();
  expect(await page.evaluate(() => navigator.clipboard.readText())).toBe(
    pinned,
  );
  await page
    .getByRole("link", {
      name: "Delver of Secrets // Insectile Aberration",
      exact: true,
    })
    .click();
  await expect(
    page.getByRole("heading", { name: "Insectile Aberration", exact: true }),
  ).toBeVisible();
  await expect(page.getByText("Flying", { exact: true })).toBeVisible();
  await expect(
    page.getByRole("heading", { name: "Eligible printings" }),
  ).toBeVisible();
  expect((await new AxeBuilder({ page }).analyze()).violations).toEqual([]);
  await page
    .getByRole("link", { name: "Inspect source and methodology" })
    .click();
  await expect(page).toHaveURL(new RegExp(`/datasets/${snapshot}$`));
  await expect(page.getByText("7 / 8", { exact: true })).toBeVisible();
  await expect(page.getByText(snapshot, { exact: true })).toBeVisible();
  expect((await new AxeBuilder({ page }).analyze()).violations).toEqual([]);
  const reopened = await context.newPage();
  await reopened.goto(pinned);
  await expect(reopened.getByLabel("Card or face name")).toHaveValue(
    "Insectile",
  );
  await expect(
    reopened.getByRole("link", {
      name: "Delver of Secrets // Insectile Aberration",
      exact: true,
    }),
  ).toBeVisible();
  await reopened.close();
  expect(outbound).toEqual([]);
});

test("joint filters, empty state and Back restore filters", async ({
  page,
}) => {
  await page.goto("/cards");
  await page.getByLabel("Sets", { exact: true }).selectOption("2x2");
  await page.getByLabel("Rarity", { exact: true }).selectOption("common");
  await page.getByRole("button", { name: "Find cards", exact: true }).click();
  await expect(
    page.getByRole("heading", { name: "No cards match this pool." }),
  ).toBeVisible();
  await page
    .getByRole("link", { name: "Clear filters", exact: true })
    .last()
    .click();
  await expect(
    page.getByRole("link", { name: "Lightning Bolt", exact: true }),
  ).toBeVisible();
  await page.goBack();
  await expect(page.getByLabel("Sets", { exact: true })).toHaveValues(["2x2"]);
  await expect(page.getByLabel("Rarity", { exact: true })).toHaveValues([
    "common",
  ]);
});

test("pagination retains the old publication after a Python refresh", async ({
  page,
}) => {
  await page.goto("/cards?limit=2");
  await expect(page).toHaveURL(/catalog_snapshot_id=catalog-/);
  const old = new URL(page.url()).searchParams.get("catalog_snapshot_id")!;
  const refresh = JSON.parse(control("refresh")) as {
    catalog_snapshot_id: string;
  };
  expect(refresh.catalog_snapshot_id).not.toBe(old);
  try {
    await page.getByRole("link", { name: "Next page" }).click();
    await expect(page).toHaveURL(new RegExp(`catalog_snapshot_id=${old}`));
    await expect(
      page.getByRole("link", {
        name: "Delver of Secrets // Insectile Aberration",
        exact: true,
      }),
    ).toBeVisible();
    await page.getByRole("link", { name: "Inspect this dataset" }).click();
    await expect(page.getByText(old, { exact: true })).toBeVisible();
  } finally {
    control(
      "rollback",
      "--target",
      old,
      "--expected",
      refresh.catalog_snapshot_id,
    );
  }
});

test("responsive discovery, loading feedback and database failure retry", async ({
  page,
}) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto("/cards");
  await expect(
    page.getByRole("heading", { name: /Find something/ }),
  ).toBeVisible();
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= innerWidth,
    ),
  ).toBe(true);
  expect((await new AxeBuilder({ page }).analyze()).violations).toEqual([]);
  await page.screenshot({
    path: "test-results/discovery-mobile.png",
    fullPage: true,
  });
  const pinned = page.url();
  await page
    .getByRole("link", {
      name: "Delver of Secrets // Insectile Aberration",
      exact: true,
    })
    .click();
  await expect(
    page.getByRole("heading", { name: "Insectile Aberration", exact: true }),
  ).toBeVisible();
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= innerWidth,
    ),
  ).toBe(true);
  expect((await new AxeBuilder({ page }).analyze()).violations).toEqual([]);
  await page.screenshot({
    path: "test-results/detail-mobile.png",
    fullPage: true,
  });
  await page
    .getByRole("link", { name: "Inspect source and methodology" })
    .click();
  await expect(page.getByText("7 / 8", { exact: true })).toBeVisible();
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= innerWidth,
    ),
  ).toBe(true);
  expect((await new AxeBuilder({ page }).analyze()).violations).toEqual([]);
  await page.screenshot({
    path: "test-results/dataset-mobile.png",
    fullPage: true,
  });
  control("unavailable");
  try {
    await page.goto(pinned);
    await expect(
      page.getByRole("heading", { name: "The catalog is taking a break." }),
    ).toBeVisible();
    await expect(
      page.getByRole("button", { name: "Retry", exact: true }),
    ).toBeVisible();
    expect((await new AxeBuilder({ page }).analyze()).violations).toEqual([]);
  } finally {
    control("available");
  }
  await page.getByRole("button", { name: "Retry", exact: true }).click();
  await expect(
    page.getByRole("heading", { name: /Find something/ }),
  ).toBeVisible();
});

test("loading feedback remains visible during a pending filter navigation", async ({
  page,
}) => {
  await page.goto("/cards");
  await expect(page).toHaveURL(/catalog_snapshot_id=catalog-/);
  let release!: () => void;
  const gate = new Promise<void>((resolve) => {
    release = resolve;
  });
  await page.route(
    (url) => url.pathname === "/cards" && url.searchParams.get("q") === "Erayo",
    async (route) => {
      await gate;
      await route.continue();
    },
  );
  await page.getByLabel("Card or face name").fill("Erayo");
  await page.getByRole("button", { name: "Find cards", exact: true }).click();
  try {
    await expect(
      page.getByRole("status").filter({ hasText: "Loading matching cards" }),
    ).toBeVisible();
  } finally {
    release();
  }
  await expect(page).toHaveURL(/q=Erayo/);
  await expect(
    page.getByRole("link", {
      name: "Erayo, Soratami Ascendant // Erayo's Essence",
      exact: true,
    }),
  ).toBeVisible();
});
