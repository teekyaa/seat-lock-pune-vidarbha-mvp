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
  // Valid JSON of the wrong shape, e.g. a bare string, is rejected too.
  const wrongShape = await request.post("/session", { headers, data: JSON.stringify("hello") });
  expect(wrongShape.status()).toBe(400);
  const missingCode = await request.post("/session", { headers, data: { phone: "9000000001" } });
  expect(missingCode.status()).toBe(400);
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

test("login says WhatsApp and offers SMS instead", async ({ page }) => {
  const bodies: unknown[] = [];
  await page.route("**/api/proxy/auth/otp/request", async (route) => {
    const body = route.request().postDataJSON();
    bodies.push(body);
    if (bodies.length === 1) {
      return route.fulfill({ status: 200, contentType: "application/json",
        body: JSON.stringify({ phone: "+919000000001", resend_after: 0, channel: "whatsapp", sms_available: true }) });
    }
    return route.fulfill({ status: 200, contentType: "application/json",
      body: JSON.stringify({ phone: "+919000000001", resend_after: 120, channel: "sms", sms_available: true }) });
  });
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto("/login");
  await page.getByLabel("Your mobile number").fill("9000000001");
  await page.getByRole("button", { name: "Send code" }).click();
  await expect(page.getByLabel(/on WhatsApp/)).toBeVisible();
  await page.getByRole("button", { name: "Not on WhatsApp? Send by SMS" }).click();
  await expect(page.getByLabel(/by SMS/)).toBeVisible();
  expect(bodies[1]).toEqual({ phone: "9000000001", channel: "sms" });
  await expect(page.getByRole("button", { name: /Resend in 1m/ })).toBeDisabled();
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBeTruthy();
});

test("login shows the exact time a block ends", async ({ page }) => {
  await page.route("**/api/proxy/auth/otp/request", (route) => route.fulfill({
    status: 429, contentType: "application/json",
    body: JSON.stringify({ code: "otp_blocked", retry_after: 86400,
      detail: "Too many code requests from this number. You can try again after Sat 7 Nov, 10:00 am IST." }),
  }));
  await page.goto("/login");
  await page.getByLabel("Your mobile number").fill("9000000001");
  await page.getByRole("button", { name: "Send code" }).click();
  await expect(page.getByText(/try again after Sat 7 Nov, 10:00 am IST/)).toBeVisible();
  await expect(page.getByRole("button", { name: "Send code" })).toBeEnabled();
});
