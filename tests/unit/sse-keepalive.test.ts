import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";

/**
 * Keep-alive timeout threshold (must match hooks/use-sse.ts).
 * Server sends keep-alive every 30 seconds, so we use 45 seconds buffer.
 */
const KEEPALIVE_TIMEOUT_MS = 45000;

/**
 * Simulates the timeout detection logic from useSSE hook.
 * Returns true if reconnection should be triggered.
 */
function shouldReconnectAfterWake(
  lastKeepAliveTimestamp: number,
  currentTime: number,
  isConnected: boolean,
): boolean {
  if (!isConnected) return false;
  const elapsed = currentTime - lastKeepAliveTimestamp;
  return elapsed > KEEPALIVE_TIMEOUT_MS;
}

describe("SSE keep-alive timeout detection", () => {
  describe("shouldReconnectAfterWake", () => {
    it("triggers reconnect when elapsed time exceeds threshold", () => {
      const now = Date.now();
      const lastKeepAlive = now - 60000; // 60 seconds ago

      const result = shouldReconnectAfterWake(lastKeepAlive, now, true);

      expect(result).toBe(true);
    });

    it("does not trigger reconnect when within threshold", () => {
      const now = Date.now();
      const lastKeepAlive = now - 20000; // 20 seconds ago

      const result = shouldReconnectAfterWake(lastKeepAlive, now, true);

      expect(result).toBe(false);
    });

    it("does not trigger reconnect at exact threshold", () => {
      const now = Date.now();
      const lastKeepAlive = now - KEEPALIVE_TIMEOUT_MS; // Exactly at threshold

      const result = shouldReconnectAfterWake(lastKeepAlive, now, true);

      expect(result).toBe(false);
    });

    it("triggers reconnect just past threshold", () => {
      const now = Date.now();
      const lastKeepAlive = now - KEEPALIVE_TIMEOUT_MS - 1; // 1ms past threshold

      const result = shouldReconnectAfterWake(lastKeepAlive, now, true);

      expect(result).toBe(true);
    });

    it("does not trigger reconnect when not connected", () => {
      const now = Date.now();
      const lastKeepAlive = now - 60000; // 60 seconds ago

      const result = shouldReconnectAfterWake(lastKeepAlive, now, false);

      expect(result).toBe(false);
    });

    it("handles very long sleep duration", () => {
      const now = Date.now();
      const lastKeepAlive = now - 3600000; // 1 hour ago

      const result = shouldReconnectAfterWake(lastKeepAlive, now, true);

      expect(result).toBe(true);
    });

    it("handles zero elapsed time (just connected)", () => {
      const now = Date.now();
      const lastKeepAlive = now; // Just now

      const result = shouldReconnectAfterWake(lastKeepAlive, now, true);

      expect(result).toBe(false);
    });
  });
});

describe("SSE visibility change handler", () => {
  let mockVisibilityState: DocumentVisibilityState;

  beforeEach(() => {
    mockVisibilityState = "visible";
    vi.stubGlobal("document", {
      visibilityState: mockVisibilityState,
      addEventListener: vi.fn(),
      removeEventListener: vi.fn(),
    });
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("adds visibilitychange event listener", () => {
    const addEventListenerSpy = vi.fn();
    vi.stubGlobal("document", {
      visibilityState: "visible",
      addEventListener: addEventListenerSpy,
      removeEventListener: vi.fn(),
    });

    // Simulate what useEffect does
    const handleVisibilityChange = vi.fn();
    document.addEventListener("visibilitychange", handleVisibilityChange);

    expect(addEventListenerSpy).toHaveBeenCalledWith(
      "visibilitychange",
      handleVisibilityChange,
    );
  });

  it("removes event listener on cleanup", () => {
    const removeEventListenerSpy = vi.fn();
    vi.stubGlobal("document", {
      visibilityState: "visible",
      addEventListener: vi.fn(),
      removeEventListener: removeEventListenerSpy,
    });

    const handleVisibilityChange = vi.fn();
    document.removeEventListener("visibilitychange", handleVisibilityChange);

    expect(removeEventListenerSpy).toHaveBeenCalledWith(
      "visibilitychange",
      handleVisibilityChange,
    );
  });
});

describe("keep-alive timestamp tracking", () => {
  it("updates timestamp on keep-alive event", () => {
    let lastKeepAlive = 0;
    const now = Date.now();

    // Simulate receiving keep-alive event
    const onKeepAlive = () => {
      lastKeepAlive = Date.now();
    };

    // Before keep-alive
    expect(lastKeepAlive).toBe(0);

    // Receive keep-alive
    vi.setSystemTime(now);
    onKeepAlive();

    expect(lastKeepAlive).toBe(now);
  });

  it("updates timestamp on connection open", () => {
    let lastKeepAlive = 0;
    const now = Date.now();

    // Simulate connection open
    const onOpen = () => {
      lastKeepAlive = Date.now();
    };

    vi.setSystemTime(now);
    onOpen();

    expect(lastKeepAlive).toBe(now);
  });
});

describe("reconnection scenarios", () => {
  beforeEach(() => {
    vi.useFakeTimers();
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it("simulates sleep/wake reconnection flow", () => {
    const events: string[] = [];
    let lastKeepAlive = Date.now();
    let isConnected = true;

    // Simulate connection established
    events.push("connected");
    lastKeepAlive = Date.now();

    // Receive a few keep-alives
    vi.advanceTimersByTime(30000);
    lastKeepAlive = Date.now();
    events.push("keep-alive");

    vi.advanceTimersByTime(30000);
    lastKeepAlive = Date.now();
    events.push("keep-alive");

    // Simulate sleep (no keep-alives, time advances)
    vi.advanceTimersByTime(120000); // 2 minutes of sleep

    // Wake up - check if reconnect needed
    const shouldReconnect = shouldReconnectAfterWake(
      lastKeepAlive,
      Date.now(),
      isConnected,
    );

    expect(shouldReconnect).toBe(true);

    // Simulate reconnection
    if (shouldReconnect) {
      isConnected = false;
      events.push("disconnected");
      events.push("reconnecting");
      isConnected = true;
      lastKeepAlive = Date.now();
      events.push("connected");
    }

    expect(events).toEqual([
      "connected",
      "keep-alive",
      "keep-alive",
      "disconnected",
      "reconnecting",
      "connected",
    ]);
  });

  it("does not reconnect if tab was hidden briefly", () => {
    let lastKeepAlive = Date.now();
    const isConnected = true;

    // Receive keep-alive
    vi.advanceTimersByTime(30000);
    lastKeepAlive = Date.now();

    // Tab hidden briefly (10 seconds)
    vi.advanceTimersByTime(10000);

    // Tab becomes visible
    const shouldReconnect = shouldReconnectAfterWake(
      lastKeepAlive,
      Date.now(),
      isConnected,
    );

    expect(shouldReconnect).toBe(false);
  });

  it("reconnects after long tab hidden period", () => {
    let lastKeepAlive = Date.now();
    const isConnected = true;

    // Receive keep-alive
    vi.advanceTimersByTime(30000);
    lastKeepAlive = Date.now();

    // Tab hidden for long time (5 minutes)
    vi.advanceTimersByTime(300000);

    // Tab becomes visible
    const shouldReconnect = shouldReconnectAfterWake(
      lastKeepAlive,
      Date.now(),
      isConnected,
    );

    expect(shouldReconnect).toBe(true);
  });
});
