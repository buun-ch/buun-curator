/**
 * Next.js instrumentation hook for OpenTelemetry tracing.
 *
 * This file is automatically loaded by Next.js at startup.
 * Only initializes tracing in Node.js runtime (not Edge).
 *
 * @see https://nextjs.org/docs/app/guides/open-telemetry
 */

export async function register() {
  // Only initialize tracing in Node.js runtime
  if (process.env.NEXT_RUNTIME === "nodejs") {
    const { initTracing } = await import("@/lib/tracing");
    initTracing();
  }
}
