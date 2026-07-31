import { test, expect } from "@playwright/test";

/**
 * Critical user-flow test (spec §11).
 *
 * Runs against a live docker-compose stack in DEMO_MODE=true. Verifies
 * the end-to-end MVP journey works: sign in → dashboard → search →
 * asset detail with quote + signal + chart.
 *
 * Precondition: `docker compose up --build` is running and reachable at
 * E2E_BASE_URL (default http://localhost:3000). The demo user must be
 * seedable via the "Continue as demo user" button on /signin.
 */

test.describe("critical flow", () => {
  test("demo login → dashboard → search → asset detail", async ({ page }) => {
    // 1. Middleware redirects an anonymous visitor to /signin
    await page.goto("/");
    await expect(page).toHaveURL(/\/signin/);
    await expect(page.getByRole("heading", { name: /sign in/i })).toBeVisible();

    // 2. Continue as demo user
    const demoButton = page.getByRole("button", { name: /continue as demo user/i });
    await expect(demoButton).toBeVisible();
    await demoButton.click();

    // 3. Landed on the dashboard
    await expect(page).toHaveURL(/\/$/);
    await expect(page.getByRole("heading", { name: /dashboard/i })).toBeVisible();

    // 4. Markets card is populated (5 calendars)
    await expect(page.getByText(/US/i).first()).toBeVisible();
    await expect(page.getByText(/CRYPTO/i).first()).toBeVisible();

    // 5. Watchlist has the seeded AAPL entry
    await expect(page.getByRole("link", { name: /AAPL/i }).first()).toBeVisible();

    // 6. Click into the asset detail page
    await page.getByRole("link", { name: /AAPL/i }).first().click();
    await expect(page).toHaveURL(/\/assets\/EQUITY%3AUS%3ANASDAQ%3AAAPL/);

    // 7. Quote card is populated (mock provider price + timestamp)
    await expect(page.getByText(/USD/).first()).toBeVisible({ timeout: 15_000 });

    // 8. Signal card renders a classification + score
    await expect(
      page.getByText(/STRONG_BULLISH|BULLISH|NEUTRAL|BEARISH|STRONG_BEARISH|INSUFFICIENT_DATA/)
        .first()
    ).toBeVisible({ timeout: 15_000 });

    // 9. Chart renders (Lightweight Charts creates a canvas)
    await expect(page.locator("canvas").first()).toBeVisible({ timeout: 15_000 });

    // 10. Signal Lab link is present + navigable
    await expect(page.getByRole("link", { name: /signal lab/i })).toBeVisible();
  });
});
