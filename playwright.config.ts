import { defineConfig, devices } from "@playwright/test";

/**
 * Playwright configuration for E2E testing.
 *
 * @see https://playwright.dev/docs/test-configuration
 */
export default defineConfig({
  testDir: "./tests/e2e",
  fullyParallel: true,
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 2 : 0,
  workers: process.env.CI ? 1 : undefined,
  reporter: "html",
  // Increase timeout for E2E tests through Toxiproxy (network fault injection)
  timeout: 60000,
  use: {
    // Base URL for tests (can be overridden by environment variable)
    // Default: E2E namespace via Toxiproxy
    baseURL:
      process.env.BASE_URL ||
      "http://buun-curator-toxiproxy.buun-curator-e2e:8080",
    trace: "on-first-retry",
    // Navigation timeout
    navigationTimeout: 30000,
  },

  projects: [
    {
      name: "chromium",
      use: { ...devices["Desktop Chrome"] },
    },
  ],

  // Run local dev server before starting tests (optional)
  // webServer: {
  //   command: "bun dev",
  //   url: "http://localhost:3000",
  //   reuseExistingServer: !process.env.CI,
  // },
});
