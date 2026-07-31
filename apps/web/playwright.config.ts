import { defineConfig, devices } from "@playwright/test";

/**
 * Playwright config for critical-flow E2E.
 *
 * These tests expect the full docker-compose stack to be up and
 * reachable at BASE_URL (default http://localhost:3000). They do NOT
 * spin up the stack themselves. In CI, gate them behind a manual
 * workflow that runs docker-compose first.
 */
const BASE_URL = process.env.E2E_BASE_URL || "http://localhost:3000";

export default defineConfig({
  testDir: "./e2e",
  timeout: 30_000,
  expect: { timeout: 5_000 },
  fullyParallel: false,
  retries: process.env.CI ? 2 : 0,
  reporter: [["list"]],
  use: {
    baseURL: BASE_URL,
    trace: "on-first-retry",
    screenshot: "only-on-failure",
    ignoreHTTPSErrors: true
  },
  projects: [
    { name: "chromium", use: { ...devices["Desktop Chrome"] } }
  ]
});
