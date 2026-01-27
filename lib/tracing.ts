/**
 * OpenTelemetry tracing configuration for Buun Curator Frontend.
 *
 * Provides optional distributed tracing with graceful degradation when
 * tracing is disabled or the collector is unavailable.
 *
 * @module lib/tracing
 */

import { OTLPTraceExporter } from "@opentelemetry/exporter-trace-otlp-grpc";
import { resourceFromAttributes } from "@opentelemetry/resources";
import { NodeSDK } from "@opentelemetry/sdk-node";
import {
  ATTR_SERVICE_NAME,
  ATTR_SERVICE_VERSION,
} from "@opentelemetry/semantic-conventions";

import { createLogger } from "@/lib/logger";

const log = createLogger("tracing");

let sdk: NodeSDK | null = null;

/** Check if tracing is enabled via environment variable. */
export function isTracingEnabled(): boolean {
  return process.env.OTEL_TRACING_ENABLED === "true";
}

/** Initialize OpenTelemetry SDK for Node.js runtime. */
export function initTracing(): void {
  if (!isTracingEnabled()) {
    log.info("Tracing disabled (OTEL_TRACING_ENABLED != true)");
    return;
  }

  const endpoint =
    process.env.OTEL_EXPORTER_OTLP_ENDPOINT || "http://localhost:4317";
  const serviceName = process.env.OTEL_SERVICE_NAME || "buun-curator-frontend";

  log.info({ serviceName, endpoint }, "Initializing tracing");

  const resource = resourceFromAttributes({
    [ATTR_SERVICE_NAME]: serviceName,
    [ATTR_SERVICE_VERSION]: process.env.APP_VERSION || "0.1.0",
    "deployment.environment": process.env.DEPLOYMENT_ENV || "development",
  });

  const traceExporter = new OTLPTraceExporter({
    url: endpoint,
  });

  sdk = new NodeSDK({
    resource,
    traceExporter,
  });

  sdk.start();
  log.info("Tracing initialized successfully");
}

/** Shutdown tracing and flush any pending spans. */
export function shutdownTracing(): Promise<void> {
  if (sdk) {
    return sdk.shutdown();
  }
  return Promise.resolve();
}
