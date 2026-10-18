import { test, expect } from "@playwright/test";
import AxeBuilder from "@axe-core/playwright";
import {
  count,
  deltaTone,
  grade,
  gradeTone,
  lift,
  liftTone,
  movement,
  percent,
  signed,
} from "../src/lib/format";

test("number and grade formatting", () => {
  expect(signed(2.43)).toBe("+2.4");
  expect(signed(-0.81)).toBe("−0.8");
  expect(signed(0.049)).toBe("0.0");
  expect(signed(-0.049)).toBe("0.0");
  expect(percent(54.12)).toBe("54.1%");
  expect(percent(-0.01)).toBe("0.0%");
  expect(lift(1.123)).toBe("1.12×");
  expect(count(33512)).toBe("33,512");
  expect([3, -2, 0].map(movement)).toEqual(["▲ 3", "▼ 2", "—"]);
  expect([90, 85, 80, 75, 70, 65, 60, 50, 45, 35, 34.9].map(grade)).toEqual([
    "A+",
    "A",
    "A−",
    "B+",
    "B",
    "B−",
    "C+",
    "C",
    "C−",
    "D",
    "F",
  ]);
  expect(["A−", "B+", "C", "D", "F"].map(gradeTone)).toEqual([
    "a",
    "b",
    "c",
    "d",
    "f",
  ]);
  expect([0.05, 0.04, -0.05].map(deltaTone)).toEqual([
    "positive",
    "neutral",
    "negative",
  ]);
  expect([1.1, 1.0, 0.96].map(liftTone)).toEqual([
    "positive",
    "neutral",
    "negative",
  ]);
});

test("primitives gallery states, keyboard behavior and accessibility", async ({
  page,
}) => {
  await page.goto("/primitives");
  await expect(
    page.getByRole("heading", { name: "Primitives", exact: true }),
  ).toBeVisible();
  expect((await new AxeBuilder({ page }).analyze()).violations).toEqual([]);

  // Tooltip: focus opens it, Esc closes it, and its text describes the trigger.
  const info = page.getByRole("button", { name: "How the grade works" });
  await info.focus();
  const tip = page
    .getByRole("tooltip")
    .filter({ hasText: "Constructed score" });
  await expect(tip).toBeVisible();
  await expect(info).toHaveAccessibleDescription(/Constructed score/);
  await page.keyboard.press("Escape");
  await expect(tip).toBeHidden();
  await page.getByRole("button", { name: "Hover or focus me" }).hover();
  await expect(
    page.getByRole("tooltip").filter({ hasText: "Below, aligned" }),
  ).toBeVisible();

  // Native inputs keep keyboard behavior; disabled ones ignore input.
  const toggle = page.getByRole("switch", { name: "In every selected format" });
  await toggle.focus();
  await page.keyboard.press("Space");
  await expect(toggle).toBeChecked();
  await expect(
    page.getByRole("switch", { name: "Unavailable" }),
  ).toBeDisabled();
  await expect(
    page.getByRole("checkbox", { name: "All sets" }),
  ).toHaveJSProperty("indeterminate", true);
  await page.getByRole("checkbox", { name: "Standard" }).check();
  await expect(page.getByRole("checkbox", { name: "Standard" })).toBeChecked();
  await page.getByRole("radio", { name: "All", exact: true }).focus();
  await page.keyboard.press("ArrowRight");
  await expect(page.getByRole("radio", { name: "Online" })).toBeChecked();

  // Underline tabs are links; the current view is marked.
  await page.getByRole("link", { name: /^Rising/ }).click();
  await expect(page).toHaveURL(/view=rising/);
  await expect(page.getByRole("link", { name: /^Rising/ })).toHaveAttribute(
    "aria-current",
    "page",
  );

  // Toast: announced in a status region, dismissible, gone after about 4s.
  await page.getByRole("button", { name: "Show success toast" }).click();
  const toast = page
    .getByRole("status")
    .filter({ hasText: "Search URL copied." });
  await expect(toast).toBeVisible();
  await page.getByRole("button", { name: "Dismiss" }).click();
  await expect(toast).toBeHidden();
  await page.getByRole("button", { name: "Show warning toast" }).click();
  await expect(page.getByText("Couldn't copy the URL.")).toBeVisible();
  await expect(page.getByText("Couldn't copy the URL.")).toBeHidden({
    timeout: 6000,
  });

  // Hover lifts a card; reduced motion keeps it in place.
  const card = page.locator(".card-frame.interactive").first();
  await card.hover();
  await expect(card).toHaveCSS("transform", "matrix(1, 0, 0, 1, 0, -5)");
  await page.emulateMedia({ reducedMotion: "reduce" });
  await page.mouse.move(0, 0);
  await card.hover();
  await expect(card).toHaveCSS("transform", "matrix(1, 0, 0, 1, 0, 0)");
});
