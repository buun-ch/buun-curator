/**
 * Unified logging for both server and browser.
 *
 * Server-side: Uses pino with pino-pretty in development, JSON in production.
 * Browser-side: Uses debug for namespace filtering via localStorage.
 *
 * Enable debug output in browser console:
 *   localStorage.debug = 'curator:*'
 *
 * Enable specific namespaces:
 *   localStorage.debug = 'curator:hooks:*'
 *
 * @module lib/logger
 */
import pino from "pino";
import createDebug from "debug";
import { trace, context } from "@opentelemetry/api";

const isServer = typeof window === "undefined";
const isDevelopment = process.env.NODE_ENV === "development";

/** Root namespace for all loggers. */
const ROOT_NAMESPACE = "curator";

/** Pino log levels. */
const LEVEL = {
  trace: 10,
  debug: 20,
  info: 30,
  warn: 40,
  error: 50,
  fatal: 60,
} as const;

/** Cache for debug instances to avoid recreating them. */
const debuggers = new Map<string, createDebug.Debugger>();

/**
 * Gets or creates a debug instance for the given namespace.
 *
 * @param namespace - The full namespace (e.g., 'curator:hooks:entries')
 * @returns Cached or new debug instance
 */
function getDebugger(namespace: string): createDebug.Debugger {
  let d = debuggers.get(namespace);
  if (!d) {
    d = createDebug(namespace);
    debuggers.set(namespace, d);
  }
  return d;
}

/**
 * Gets OpenTelemetry trace context and component from the current span.
 *
 * @returns Object with component, trace_id, span_id for structured logging
 */
function getTraceContext(): Record<string, string> {
  if (!isServer) return {};

  const result: Record<string, string> = { component: "frontend" };

  const span = trace.getSpan(context.active());
  if (span) {
    const spanContext = span.spanContext();
    result.trace_id = spanContext.traceId;
    result.span_id = spanContext.spanId;
  }
  return result;
}

/**
 * Root logger instance.
 *
 * Server: Uses pino-pretty in development, JSON in production.
 * Browser: Routes to debug library for namespace filtering.
 */
export const logger = pino({
  level: process.env.LOG_LEVEL || (isDevelopment ? "debug" : "info"),

  // Use "event" instead of "msg" to match worker/agent (structlog convention)
  messageKey: "event",

  // Format level as string instead of number
  formatters: {
    level: (label) => ({ level: label }),
  },

  // Use ISO timestamp format with "timestamp" field name (matches worker/agent)
  timestamp: () => `,"timestamp":"${new Date().toISOString()}"`,

  // Mixin to add OpenTelemetry trace context to every log entry (server-side only)
  mixin: getTraceContext,

  // Browser-side: route to debug library
  browser: {
    asObject: true,
    write: (logObj: object) => {
      const {
        level,
        event,
        module,
        time: _time,
        ...rest
      } = logObj as Record<string, unknown>;
      const levelNum = typeof level === "number" ? level : LEVEL.info;
      const namespace = `${ROOT_NAMESPACE}:${module || "app"}`;
      const message = String(event || "");
      const hasData = Object.keys(rest).length > 0;

      // error/fatal: always output via console.error
      if (levelNum >= LEVEL.error) {
        if (hasData) {
          console.error(`[${namespace}] ${message}`, rest);
        } else {
          console.error(`[${namespace}] ${message}`);
        }
        return;
      }

      // warn: always output via console.warn
      if (levelNum >= LEVEL.warn) {
        if (hasData) {
          console.warn(`[${namespace}] ${message}`, rest);
        } else {
          console.warn(`[${namespace}] ${message}`);
        }
        return;
      }

      // info/debug/trace: filter via debug library
      const debug = getDebugger(namespace);
      if (debug.enabled) {
        if (hasData) {
          debug(message, rest);
        } else {
          debug(message);
        }
      }
    },
  },
});

/**
 * Creates a child logger with a module context.
 *
 * @param module - The module name (e.g., 'sse', 'hooks:entries', 'api:feeds')
 * @returns A child logger with the module context
 *
 * @example
 * const log = createLogger('sse');
 * log.info('connected');
 * // Server: [14:30:00] INFO (curator:sse): connected
 * // Browser: curator:sse connected +0ms (if localStorage.debug includes it)
 *
 * @example
 * const log = createLogger('hooks:entries');
 * log.debug({ count: 10 }, 'fetching entries');
 * // Filtered by localStorage.debug = 'curator:hooks:*'
 */
export function createLogger(module: string): pino.Logger {
  return logger.child({ module });
}

/** Pre-configured loggers for common modules. */
export const log = {
  sse: createLogger("sse"),
  api: createLogger("api"),
  temporal: createLogger("temporal"),
  db: createLogger("db"),
  hooks: createLogger("hooks"),
  components: createLogger("components"),
} as const;
