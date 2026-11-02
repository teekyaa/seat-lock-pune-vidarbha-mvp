import { test, expect } from "@playwright/test";

test("login handles SMS request and verification errors without sending SMS", async ({ page }) => {
  await page.route("**/api/proxy/auth/otp/request", (route) => route.fulfill({
    status: 200, contentType: "application/json",
    body: JSON.stringify({ phone: "+919000000001", resend_after: 60 }),
  }));
  await page.route("**/session", (route) => route.fulfill({
    status: 400, contentType: "application/json", body: JSON.stringify({ detail: "That code does not match." }),
  }));
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto("/login?next=/me");
  await page.getByLabel("Your mobile number").fill("9000000001");
  await page.getByRole("button", { name: "Send code" }).click();
  await expect(page.getByLabel(/Enter the code sent/)).toBeVisible();
  await page.getByLabel(/Enter the code sent/).fill("123456");
  await expect(page.getByText("That code does not match.")).toBeVisible();
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBeTruthy();
});

test("cross-origin session and proxy writes are rejected", async ({ request }) => {
  for (const path of ["/session", "/api/proxy/me"]) {
    const response = await request.post(path, {
      headers: { Origin: "https://attacker.invalid" },
      data: {},
    });
    expect(response.status()).toBe(403);
  }
});

test("session rejects malformed and oversized requests", async ({ request, baseURL }) => {
  const headers = { Origin: new URL(baseURL!).origin, "Content-Type": "application/json" };
  const malformed = await request.post("/session", { headers, data: "{" });
  expect(malformed.status()).toBe(400);
  const oversized = await request.post("/session", { headers, data: "x".repeat(5000) });
  expect(oversized.status()).toBe(413);
});

test("login reports a network failure instead of remaining busy", async ({ page }) => {
  await page.route("**/api/proxy/auth/otp/request", (route) => route.fulfill({
    status: 200, contentType: "application/json", body: JSON.stringify({ phone: "+919000000001", resend_after: 60 }),
  }));
  await page.route("**/session", (route) => route.abort());
  await page.goto("/login");
  await page.getByLabel("Your mobile number").fill("9000000001");
  await page.getByRole("button", { name: "Send code" }).click();
  await page.getByLabel(/Enter the code sent/).fill("123456");
  await expect(page.getByText("Could not connect. Please try again.")).toBeVisible();
});
