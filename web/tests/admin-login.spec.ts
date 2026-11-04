import { expect, test } from "@playwright/test";

test("administrator pages require separate sign-in and work on mobile", async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto("/control");
  await expect(page).toHaveURL(/\/control\/login$/);
  await page.waitForLoadState("networkidle");
  await expect(page.getByRole("heading", { name: "Admin sign in" })).toBeVisible();
  await expect(page.getByRole("navigation", { name: "Main" })).toHaveCount(0);
  await page.getByRole("button", { name: "Dark mode" }).click();
  await expect(page.locator(".control-shell")).toHaveAttribute("data-theme", "dark");
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBeTruthy();
});

test("admin login displays an error without disclosing credentials", async ({ page, request }) => {
  const rejected = await request.post("/admin-session", { headers: { Origin: "https://untrusted.invalid" }, data: {} });
  expect(rejected.status()).toBe(403);
  await page.route("**/admin-session", (route) => route.fulfill({
    status: 401, contentType: "application/json", body: JSON.stringify({ detail: "Invalid credentials." }),
  }));
  await page.goto("/control/login");
  await page.getByLabel("Email").fill("operator@example.invalid");
  await page.getByLabel("Password").fill("synthetic-password");
  await page.getByLabel("Authenticator code").fill("123456");
  await page.getByRole("button", { name: "Sign in", exact: true }).click();
  await expect(page.getByText("Invalid credentials.")).toBeVisible();
  await expect(page.getByText("synthetic-password")).toHaveCount(0);
});
