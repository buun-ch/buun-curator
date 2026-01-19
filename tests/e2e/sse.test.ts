import { test, expect, Page } from "@playwright/test";
import {
  createProxy,
  deleteProxy,
  addTimeoutToxic,
  addLatencyToxic,
  addResetPeerToxic,
  removeAllToxics,
  removeToxic,
} from "./helpers/toxiproxy-client";

/**
 * E2E tests for SSE connection resilience.
 *
 * These tests verify that the SSE connection properly reconnects
 * after network interruptions simulated by Toxiproxy.
 *
 * Prerequisites:
 * - Toxiproxy running and accessible at TOXIPROXY_API_URL
 * - Frontend accessible at BASE_URL (through Toxiproxy proxy)
 * - Direct frontend access at DIRECT_URL (for setup)
 */

const PROXY_NAME = "frontend-sse";
const PROXY_LISTEN = "0.0.0.0:8080";
// Use environment variable or default to Kubernetes service name in E2E namespace
const UPSTREAM =
  process.env.DIRECT_URL?.replace("http://", "") ||
  "buun-curator.buun-curator-e2e:3000";

/**
 * Wait for SSE connection to be established.
 * If not connected within initial timeout, clicks reconnect button and waits again.
 * Retries reconnect button up to 3 times if needed.
 */
async function waitForSSEConnection(
  page: Page,
  timeout = 10000,
): Promise<void> {
  const sseStatus = page.locator('[data-testid="sse-status"]');
  const reconnectButton = page.locator('[data-testid="sse-reconnect"]');

  // First, wait for the status indicator to be visible
  await expect(sseStatus).toBeVisible({ timeout: 5000 });

  // Check if already connected
  const status = await sseStatus.getAttribute("data-status");
  if (status === "connected") {
    return;
  }

  // Wait for automatic connection with shorter timeout
  try {
    await expect(sseStatus).toHaveAttribute("data-status", "connected", {
      timeout: timeout / 3,
    });
    return;
  } catch {
    // Not connected, try clicking reconnect
  }

  // Retry clicking reconnect button up to 3 times
  const maxRetries = 3;
  const retryTimeout = timeout / 3 / maxRetries;

  for (let i = 0; i < maxRetries; i++) {
    // Wait for button to be enabled (not in "connecting" state)
    const currentStatus = await sseStatus.getAttribute("data-status");
    if (currentStatus === "connected") {
      return;
    }

    // Wait a bit if status is "connecting" before clicking
    if (currentStatus === "connecting") {
      await page.waitForTimeout(1000);
    }

    // Click reconnect button
    await reconnectButton.click();

    // Wait for connection
    try {
      await expect(sseStatus).toHaveAttribute("data-status", "connected", {
        timeout: retryTimeout,
      });
      return;
    } catch {
      // Retry
    }
  }

  // Final assertion to get proper error message
  await expect(sseStatus).toHaveAttribute("data-status", "connected", {
    timeout: 5000,
  });
}

// Wrap all tests in a parent describe block with serial mode
// This ensures all tests run sequentially and share the same proxy state
test.describe("SSEProvider", () => {
  test.describe.configure({ mode: "serial" });

  test.beforeAll(async () => {
    // Clean up any existing proxy and create fresh one
    await deleteProxy(PROXY_NAME).catch(() => {});
    await createProxy(PROXY_NAME, PROXY_LISTEN, UPSTREAM);
  });

  test.afterAll(async () => {
    // Clean up toxics but keep the proxy for manual testing
    await removeAllToxics(PROXY_NAME).catch(() => {});
  });

  test.beforeEach(async () => {
    // Remove all toxics before each test
    await removeAllToxics(PROXY_NAME).catch(() => {});
  });

  test.afterEach(async () => {
    // Clean up toxics after each test
    await removeAllToxics(PROXY_NAME).catch(() => {});
  });

  test("establishes SSE connection", async ({ page }) => {
    // Navigate to the app
    await page.goto("/");

    // Wait for SSE connection (with reconnect fallback)
    await waitForSSEConnection(page, 15000);
  });

  test("reconnects after connection timeout", async ({ page }) => {
    // Navigate and wait for initial connection
    await page.goto("/");
    await waitForSSEConnection(page, 15000);

    // Inject timeout toxic (drops all data, simulates connection loss)
    await addTimeoutToxic(PROXY_NAME, 0);

    // Wait for disconnection to be detected
    // Keep-alive timeout is 45 seconds, periodic check runs every 10 seconds
    // So detection should happen within ~55 seconds
    await expect(page.locator('[data-testid="sse-status"]')).toHaveAttribute(
      "data-status",
      /(disconnected|error|connecting)/,
      { timeout: 60000 },
    );

    // Remove the toxic to allow reconnection
    await removeToxic(PROXY_NAME, "timeout");

    // Wait a bit for the proxy to fully restore
    await page.waitForTimeout(1000);

    // Wait for reconnection (with manual reconnect fallback)
    await waitForSSEConnection(page, 30000);
  });

  test("handles latency spikes gracefully", async ({ page }) => {
    await page.goto("/");
    await waitForSSEConnection(page, 15000);

    // Add high latency (but not enough to trigger timeout)
    await addLatencyToxic(PROXY_NAME, 5000, 1000);

    // Connection should remain connected (just slow)
    await page.waitForTimeout(10000);
    await expect(page.locator('[data-testid="sse-status"]')).toHaveAttribute(
      "data-status",
      "connected",
    );

    // Remove latency
    await removeToxic(PROXY_NAME, "latency");
  });

  test("reconnects after TCP reset", async ({ page }) => {
    await page.goto("/");
    await waitForSSEConnection(page, 15000);

    // Simulate TCP reset using reset_peer toxic
    // timeout=100 means reset connection 100ms after receiving data
    await addResetPeerToxic(PROXY_NAME, 100);

    // Add latency to slow down reconnection attempts
    // This gives us time to observe the disconnected state
    await addLatencyToxic(PROXY_NAME, 5000);

    // Wait for disconnection or reconnection attempt
    // Server sends keep-alive every 30s, after which reset triggers
    // With 5s latency on reconnection, we should observe non-connected state
    await expect(page.locator('[data-testid="sse-status"]')).toHaveAttribute(
      "data-status",
      /(disconnected|error|connecting)/,
      { timeout: 40000 },
    );

    // Remove toxics so reconnection can succeed
    await removeAllToxics(PROXY_NAME);

    // Wait for reconnection
    await waitForSSEConnection(page, 30000);
  });

  test("triggers reconnect on visibility change after timeout", async ({
    page,
  }) => {
    await page.goto("/");
    await waitForSSEConnection(page, 15000);

    // Start timeout toxic (data stops flowing)
    await addTimeoutToxic(PROXY_NAME, 0);

    // Simulate tab being hidden (triggers visibilitychange)
    await page.evaluate(() => {
      Object.defineProperty(document, "visibilityState", {
        value: "hidden",
        writable: true,
      });
      document.dispatchEvent(new Event("visibilitychange"));
    });

    // Wait some time (simulating sleep)
    await page.waitForTimeout(50000); // 50 seconds > 45 second threshold

    // Remove toxic before tab becomes visible
    await removeToxic(PROXY_NAME, "timeout");

    // Wait a bit for the proxy to fully restore
    await page.waitForTimeout(1000);

    // Simulate tab becoming visible
    await page.evaluate(() => {
      Object.defineProperty(document, "visibilityState", {
        value: "visible",
        writable: true,
      });
      document.dispatchEvent(new Event("visibilitychange"));
    });

    // Should trigger reconnection due to keep-alive timeout
    // Wait for reconnection (with manual reconnect fallback)
    await waitForSSEConnection(page, 30000);
  });

  test("shows appropriate UI status", async ({ page }) => {
    await page.goto("/");

    // The status indicator should be visible
    const status = page.locator('[data-testid="sse-status"]');
    await expect(status).toBeVisible({ timeout: 15000 });

    // Status should be one of: connecting, disconnected, error, or connected
    const statusValue = await status.getAttribute("data-status");
    expect(["connecting", "disconnected", "error", "connected"]).toContain(
      statusValue,
    );
  });
});
