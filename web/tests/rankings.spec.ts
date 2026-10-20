import { test, expect, type Page } from "@playwright/test";
import AxeBuilder from "@axe-core/playwright";

// verify publishes a SYNTHETIC TopDeck run over the seed catalog's cards before
// these journeys: two events, seven decks, Lightning Bolt in four of them.
const results = (page: Page) =>
  page.getByRole("region", { name: "Modern rankings" }).getByRole("status");
const preview = (page: Page) =>
  page.getByRole("complementary", { name: "Selected card" });
const search = (page: Page) =>
  page.getByRole("searchbox", { name: "Search ranked cards" });

test.beforeEach(async ({ page }) => {
  await page.route("https://cards.scryfall.io/**", (route) =>
    route.fulfill({
      contentType: "image/svg+xml",
      body: '<svg xmlns="http://www.w3.org/2000/svg" width="488" height="680"><rect width="488" height="680" fill="#e7e3d8"/></svg>',
    }),
  );
});

test("Modern rankings show the published run, its credit and every ranked card", async ({
  page,
}) => {
  await page.goto("/cards");
  await page
    .getByRole("navigation", { name: "Main" })
    .getByRole("link", { name: "Rankings" })
    .click();
  await expect(page).toHaveURL(/\/rankings$/);
  await expect(
    page.getByRole("heading", { level: 1, name: "Modern" }),
  ).toBeVisible();
  await expect(
    page.getByText("Non-rotating · Eighth Edition forward · 1v1"),
  ).toBeVisible();
  await expect(
    page
      .getByRole("main")
      .getByText(/^Updated (just now|\d+ minutes? ago) · TopDeck\.gg$/),
  ).toBeVisible();
  await expect(
    page.getByRole("main").getByRole("link", { name: "TopDeck.gg" }),
  ).toHaveAttribute("href", "https://topdeck.gg");
  await expect(
    page.getByRole("contentinfo").getByRole("link", { name: "TopDeck.gg" }),
  ).toHaveAttribute("href", "https://topdeck.gg");
  await expect(page.getByText("Mar 1 – Aug 31, 2026")).toBeVisible();
  await expect(results(page)).toHaveText("1–8 of 8 ranked cards");

  await expect(
    page.getByRole("main").getByText("Matches", { exact: true }),
  ).toBeVisible();

  const table = page.getByRole("table");
  await expect(table.getByRole("columnheader")).toHaveText([
    "#",
    "Card",
    /Grade/,
    /Price/,
    "Grade per $",
    "Win rate vs field",
    "Meta share",
    "Top cut",
    "Trend · 6 mo",
    "Most played in",
  ]);
  const rows = table.getByRole("row");
  await expect(rows).toHaveCount(9);
  await expect(rows.nth(1)).toContainText("Lightning Bolt");
  await expect(rows.nth(1).getByRole("cell").first()).toHaveText(/^1/);
  await expect(rows.nth(1).getByLabel("Grade A+")).toBeVisible();
  await expect(rows.nth(1)).toContainText("93.8");
  await expect(rows.nth(1)).toContainText("+30.0%");
  await expect(rows.nth(1)).toContainText("80.0% WR");
  await expect(rows.nth(1)).toContainText("57.1%");
  await expect(rows.nth(1)).toContainText("2.00×");
  // The seed's own Scryfall response prices Lightning Bolt's cheapest printing.
  await expect(rows.nth(1)).toContainText("$0.95");
  await expect(rows.nth(1)).toContainText("Burn");
  await expect(table).not.toContainText("Island");
  await expect(
    page.getByRole("row", { name: /Synthetic Unlisted Card/ }),
  ).toContainText("Not in this catalog");

  await expect(preview(page)).toContainText("Rank 1");
  await expect(preview(page)).toContainText("Top 13%");
  await expect(
    preview(page).getByRole("link", { name: "Open card: Lightning Bolt" }),
  ).toBeVisible();

  const podium = page.getByRole("region", { name: "Top ranked cards" });
  await expect(
    podium.getByRole("link", { name: "Rank 1: Lightning Bolt" }),
  ).toBeVisible();

  const vintage = page
    .getByRole("navigation", { name: "Formats" })
    .getByRole("link", { name: /Vintage/ });
  await expect(vintage).toHaveAttribute("aria-disabled", "true");
  expect((await new AxeBuilder({ page }).analyze()).violations).toEqual([]);
});

test("filters apply at once and keep overall ranks, and a card opens its catalog page", async ({
  page,
}) => {
  await page.goto("/rankings");
  const type = page.getByLabel("Card type");
  await type.focus();
  await type.selectOption("instant");
  await expect(page).toHaveURL(/type=instant/);
  // The toolbar is not rebuilt, so the control keeps focus.
  await expect(type).toBeFocused();
  await expect(
    page.getByRole("region", { name: "Top ranked cards" }),
  ).toHaveCount(0);
  const fire = page.getByRole("row", { name: /Fire \/\/ Ice/ });
  await expect(fire.getByRole("cell").first()).toHaveText(/^4/);
  await expect(page.getByRole("table")).not.toContainText("Bruna");

  await search(page).fill("bruna");
  await search(page).press("Enter");
  await expect(page).toHaveURL(/q=bruna/);
  await expect(page).toHaveURL(/type=instant/);
  await expect(results(page)).toHaveText("No ranked cards match");
  await type.selectOption("");
  await expect(results(page)).toHaveText("1–1 of 1 ranked card");
  await expect(search(page)).toHaveValue("bruna");
  await page
    .getByRole("link", { name: "Bruna, the Fading Light" })
    .first()
    .click();
  await expect(
    page.getByRole("heading", { level: 1, name: "Bruna, the Fading Light" }),
  ).toBeVisible();
});

test("the grading menu re-ranks by signature score and the choice follows every link", async ({
  page,
}) => {
  await page.goto("/rankings");
  const grading = page.getByLabel("Grading");
  await expect(grading).toHaveValue("");
  await expect(grading.getByRole("option")).toHaveText([
    "Constructed score",
    "Signature score",
    "Relative volume",
  ]);
  await grading.selectOption("signature-score");
  await expect(page).toHaveURL(/method=signature-score/);
  await expect(
    page.getByText(/how much it belongs to one strategy/),
  ).toBeVisible();
  // Fire // Ice is only ever Izzet Tempo; Lightning Bolt splits between two archetypes.
  const podium = page.getByRole("region", { name: "Top ranked cards" });
  await expect(
    podium.getByRole("link", { name: "Rank 1: Fire // Ice" }),
  ).toBeVisible();
  await expect(podium).toContainText("Izzet Tempo");
  const rows = page.getByRole("table").getByRole("row");
  await expect(rows.nth(1).getByLabel("Grade A+")).toBeVisible();
  await expect(rows.nth(1)).toContainText("93.8");
  await expect(
    page
      .getByRole("row", { name: /Lightning Bolt/ })
      .getByRole("cell")
      .first(),
  ).toHaveText(/^5/);

  await page
    .getByRole("columnheader", { name: /Win rate vs field/ })
    .getByRole("link")
    .click();
  await expect(page).toHaveURL(/sort=win_rate/);
  await expect(page).toHaveURL(/method=signature-score/);
  await expect(grading).toHaveValue("signature-score");
  await expect(
    page
      .getByRole("navigation", { name: "Formats" })
      .getByRole("link", { name: /Legacy/ }),
  ).toHaveAttribute("href", /method=signature-score/);

  await grading.selectOption("");
  await expect(page).not.toHaveURL(/method=/);
  await expect(page).toHaveURL(/sort=win_rate/);
  expect((await new AxeBuilder({ page }).analyze()).violations).toEqual([]);
});

test("an empty result explains itself inside the table and clears every filter", async ({
  page,
}) => {
  await page.goto("/rankings?q=nothing-matches&color=G");
  const rankings = page.getByRole("region", { name: "Modern rankings" });
  await expect(
    rankings.getByRole("heading", { level: 3, name: "No ranked cards match." }),
  ).toBeVisible();
  await expect(preview(page)).toHaveCount(0);
  await expect(search(page)).toHaveValue("nothing-matches");
  await rankings.getByRole("link", { name: "Clear filters" }).click();
  await expect(results(page)).toHaveText("1–8 of 8 ranked cards");
  await expect(page).not.toHaveURL(/q=|color=/);
  await expect(search(page)).toHaveValue("");
  await expect(page.getByRole("checkbox", { name: "Green" })).not.toBeChecked();
  expect((await new AxeBuilder({ page }).analyze()).violations).toEqual([]);
});

test("hovering a row previews its card, the header explains the method, and a row opens its card", async ({
  page,
}) => {
  await page.goto("/rankings");
  await page.getByRole("row", { name: /Fire \/\/ Ice/ }).hover();
  await expect(preview(page)).toContainText("Rank 4");

  await page.getByRole("button", { name: "About this score" }).hover();
  await expect(page.getByRole("tooltip")).toContainText("Constructed score");

  await page
    .getByRole("row", { name: /Lightning Bolt/ })
    .getByRole("cell")
    .nth(3)
    .click();
  await expect(
    page.getByRole("heading", { level: 1, name: "Lightning Bolt" }),
  ).toBeVisible();
});

test("loading more and paging stay on the pinned run", async ({ page }) => {
  await page.goto("/rankings?sort=name&limit=3");
  await expect(results(page)).toHaveText("1–3 of 8 ranked cards");
  await page.getByRole("link", { name: "Load 25 more" }).click();
  await expect(page).toHaveURL(/score_run_id=scores-[0-9a-f]{64}/);
  await expect(page).toHaveURL(/limit=28/);
  await expect(results(page)).toHaveText("1–8 of 8 ranked cards");

  await page.goto("/rankings?sort=name&limit=3&offset=3");
  await expect(results(page)).toHaveText("4–6 of 8 ranked cards");
  await page.getByRole("link", { name: "Next 3" }).click();
  await expect(results(page)).toHaveText("7–8 of 8 ranked cards");
  await page.getByRole("link", { name: "Previous" }).click();
  await expect(results(page)).toHaveText("4–6 of 8 ranked cards");
});

test("column headers sort and the view tabs count risers and fallers", async ({
  page,
}) => {
  await page.goto("/rankings");
  const views = page.getByRole("navigation", { name: "Views" });
  await expect(views.getByRole("link")).toHaveText([
    "All8",
    "Risers0",
    "Fallers0",
  ]);
  const header = page.getByRole("columnheader", { name: /Win rate vs field/ });
  await header.getByRole("link").click();
  await expect(page).toHaveURL(/sort=win_rate/);
  await expect(header).toHaveAttribute("aria-sort", "descending");
  const rows = page.getByRole("table").getByRole("row");
  await expect(rows.nth(1)).toContainText("Bonecrusher Giant");
  await header.getByRole("link").click();
  await expect(page).toHaveURL(/order=asc/);
  await expect(header).toHaveAttribute("aria-sort", "ascending");
  await expect(rows.nth(1)).toContainText("Bruna, the Fading Light");
  await views.getByRole("link", { name: /Risers/ }).click();
  await expect(page).toHaveURL(/view=risers/);
  await expect(results(page)).toHaveText("No ranked cards match");
});

test("the overall tab grades each card across every published format", async ({
  page,
}) => {
  await page.goto("/rankings?format=Modern&method=signature-score");
  const overall = page
    .getByRole("navigation", { name: "Formats" })
    .getByRole("link", { name: /Overall/ });
  // The overall run has its own grading, so another format's does not follow.
  await expect(overall).toHaveAttribute("href", "/rankings?format=Overall");
  await overall.click();
  await expect(
    page.getByRole("heading", { level: 1, name: "Overall" }),
  ).toBeVisible();
  await expect(
    page.getByText("Every format at once · weighted by decklists"),
  ).toBeVisible();
  await expect(page.getByLabel("Grading")).toHaveCount(0);

  const table = page.getByRole("table");
  await expect(table.getByRole("columnheader")).toHaveText([
    "#",
    "Card",
    /Grade/,
    /Price/,
    "Grade per $",
    "Vs field",
    "Decklists",
    "Top cut",
    "Graded in",
  ]);
  // verify combines only the synthetic Modern run, so each card is graded there.
  const bolt = page.getByRole("row", { name: /Lightning Bolt/ });
  await expect(bolt.getByLabel("Grade A+")).toBeVisible();
  await expect(bolt).toContainText("+30.0%");
  await expect(bolt).not.toContainText("WR");
  await expect(bolt).toContainText("Modern");
  await expect(preview(page)).toContainText("Graded in");
  expect((await new AxeBuilder({ page }).analyze()).violations).toEqual([]);
});

test("a format without published rankings explains itself", async ({
  page,
}) => {
  await page.goto("/rankings?format=Vintage");
  await expect(
    page.getByRole("heading", {
      level: 1,
      name: "No rankings are published for this format yet.",
    }),
  ).toBeVisible();
  await page.getByRole("link", { name: "Back to rankings" }).click();
  await expect(
    page.getByRole("heading", { level: 1, name: "Modern" }),
  ).toBeVisible();
  expect((await new AxeBuilder({ page }).analyze()).violations).toEqual([]);
});
