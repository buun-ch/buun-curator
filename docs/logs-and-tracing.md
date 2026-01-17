# Logs and Tracing

This document describes the logging and distributed tracing architecture for Buun Curator.

## Overview

Buun Curator uses structured JSON logging with OpenTelemetry tracing across all components.
Logs include trace context (`trace_id`, `span_id`) for correlation with traces in Grafana.

| Component | Language   | Logging Library | Tracing                  |
| --------- | ---------- | --------------- | ------------------------ |
| Frontend  | TypeScript | pino            | OpenTelemetry SDK        |
| Worker    | Python     | structlog       | OpenTelemetry + Temporal |
| Agent     | Python     | structlog       | OpenTelemetry + FastAPI  |

## Log Format

All components output JSON logs with consistent field names for unified querying in Grafana/Loki.

### Common Fields

| Field       | Type   | Description                                               |
| ----------- | ------ | --------------------------------------------------------- |
| `event`     | string | Log message                                               |
| `level`     | string | Log level (`debug`, `info`, `warning`, `error`)           |
| `timestamp` | string | ISO 8601 timestamp (e.g., `2026-01-15T13:07:48.157413Z`)  |
| `component` | string | Component name (`frontend`, `worker`, `agent`)            |
| `trace_id`  | string | OpenTelemetry trace ID (32 hex chars)                     |
| `span_id`   | string | OpenTelemetry span ID (16 hex chars)                      |

### Frontend Log Format

```json
{
  "level": "info",
  "timestamp": "2026-01-15T13:01:15.634Z",
  "event": "Refetch started",
  "module": "api",
  "component": "frontend",
  "trace_id": "def87323463a4931dac99ea62de1fb00",
  "span_id": "1234567890abcdef",
  "entryId": "01KEYBT6D3YRV8G21A1VNMVN0A"
}
```

**Frontend-specific fields:**

- `module`: Logger module name (e.g., `api`, `sse`, `hooks`)

### Worker Log Format

```json
{
  "event": "Processing entry",
  "level": "info",
  "logger": "buun_curator.activities.content_fetcher",
  "timestamp": "2026-01-15T10:30:00.000000Z",
  "component": "worker",
  "trace_id": "def87323463a4931dac99ea62de1fb00",
  "span_id": "fedcba0987654321",
  "entry_id": "01KEYBT6D3YRV8G21A1VNMVN0A"
}
```

**Worker-specific fields:**

- `logger`: Python logger name

### Agent Log Format

```json
{
  "event": "Processing chat request",
  "level": "info",
  "logger": "buun_curator_agent.routes.chat",
  "timestamp": "2026-01-15T10:30:00.000000Z",
  "component": "agent",
  "trace_id": "abc12345678901234567890123456789",
  "span_id": "0123456789abcdef",
  "user_id": "user-123"
}
```

## Tracing Architecture

```text
┌─────────────────────────────────────────────────────────────────────────────┐
│                              Grafana                                        │
│  ┌─────────────┐    ┌─────────────┐    ┌─────────────┐                      │
│  │   Tempo     │◄───│ Trace-to-   │───►│    Loki     │                      │
│  │  (Traces)   │    │   Logs      │    │   (Logs)    │                      │
│  └─────────────┘    └─────────────┘    └─────────────┘                      │
└───────▲─────────────────────────────────────────────────────────────────────┘
        │ OTLP gRPC
        │
┌───────┴─────────────────────────────────────────────────────────────────────┐
│                           Kubernetes Cluster                                │
│                                                                             │
│  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐              │
│  │    Frontend     │  │     Worker      │  │     Agent       │              │
│  │   (Next.js)     │  │   (Temporal)    │  │   (FastAPI)     │              │
│  │                 │  │                 │  │                 │              │
│  │  pino + OTEL    │  │ structlog+OTEL  │  │ structlog+OTEL  │              │
│  │  trace_id ✓     │  │ trace_id ✓      │  │ trace_id ✓      │              │
│  └────────┬────────┘  └────────┬────────┘  └────────┬────────┘              │
│           │                    │                    │                       │
│           └────────────────────┼────────────────────┘                       │
│                                │                                            │
│                     W3C Trace Context                                       │
│                    (traceparent header)                                     │
└─────────────────────────────────────────────────────────────────────────────┘
```

### Trace Context Propagation

Traces are propagated between components using W3C Trace Context (`traceparent` header):

1. **Frontend → Worker**: HTTP request to trigger Temporal workflow
2. **Worker activities**: Temporal's TracingInterceptor propagates context
3. **Frontend → Agent**: HTTP request to AI chat endpoint

## Configuration

### Environment Variables

| Variable                       | Component | Description                                        |
| ------------------------------ | --------- | -------------------------------------------------- |
| `OTEL_TRACING_ENABLED`         | All       | Enable/disable tracing (`true`/`false`)            |
| `OTEL_SERVICE_NAME`            | All       | Service name for traces                            |
| `OTEL_EXPORTER_OTLP_ENDPOINT`  | All       | Tempo OTLP endpoint (e.g., `http://tempo:4317`)    |
| `LOG_LEVEL`                    | All       | Log level (`DEBUG`, `INFO`, `WARNING`, `ERROR`)    |
| `ENVIRONMENT`                  | All       | Environment name (`development`, `production`)     |

### Helm Values

```yaml
tracing:
  enabled: true
  frontend:
    serviceName: buun-curator  # Defaults to release name
  worker:
    serviceName: buun-curator
  agent:
    serviceName: buun-curator
```

## Grafana Integration

### Trace-to-Logs

Grafana Tempo is configured to link traces to logs in Loki:

1. Open a trace in Grafana Tempo
2. Click "Logs for this span" to view correlated logs
3. Logs are filtered by `trace_id` automatically

### Loki Queries

Filter logs by component:

```logql
{service_name="buun-curator"} | json | component="worker"
```

Filter logs by trace:

```logql
{service_name="buun-curator"} | json | trace_id="def87323463a4931dac99ea62de1fb00"
```

Query structured fields:

```logql
{service_name="buun-curator"} | json | level="error"
```

## Local Log Monitoring

For local development and debugging, use [stern](https://github.com/stern/stern) with
[Kelora](https://www.kelora.dev) to view structured logs from Kubernetes pods.

### Basic Monitoring

View logs with key fields:

```bash
stern -o raw . | kelora -k component,level,event
```

This displays a compact view showing only `component`, `level`, and `event` fields.

### Debugging

Inspect full log structure:

```bash
stern -o raw . | kelora -F inspect
```

This shows the complete JSON structure of each log entry, useful for debugging
log format issues or discovering available fields.

### Installation

```bash
# Install stern
brew install stern

# Install kelora
cargo install kelora
```

## Structured Logging Best Practices

### Use Keyword Arguments

Pass data as structured fields, not embedded in strings:

```python
# Good: Structured fields
logger.info(
    "Evaluation result",
    success=True,
    evaluated=1,
    scores={"batch_faithfulness": 1.0, "batch_answer_relevancy": 0.21},
)

# Bad: String interpolation
logger.info(f"Evaluation result: success=True, evaluated=1, scores={scores}")
```

### Output Example

Good (queryable):

```json
{
  "event": "Evaluation result",
  "success": true,
  "evaluated": 1,
  "scores": {
    "batch_faithfulness": 1.0,
    "batch_answer_relevancy": 0.21
  },
  "level": "info",
  "timestamp": "2026-01-15T13:07:48.157413Z",
  "component": "worker"
}
```

Bad (not queryable):

```json
{
  "event": "Evaluation result: success=True, evaluated=1, scores={'batch_faithfulness': 1.0}",
  "level": "info",
  "timestamp": "2026-01-15T13:07:48.157413Z",
  "component": "worker"
}
```

## Worker Logging: workflow.logger vs structlog

In the Worker component, different loggers are used depending on whether code runs inside
or outside Temporal's workflow sandbox.

### Summary

| Location | Logger | Syntax |
| -------- | ------ | ------ |
| **Workflows** | `workflow.logger` | `workflow.logger.info("msg", extra={"key": value})` |
| **Activities** | `structlog` / `logging.getLogger()` | `logger.info("msg", key=value)` |
| **Services** | `structlog` / `logging.getLogger()` | `logger.info("msg", key=value)` |

### Why the Difference?

**Workflows (`workflow.logger`)**

- Run inside Temporal's workflow sandbox (restricted environment)
- `workflow.logger` is a wrapper around Python's standard `logging.LoggerAdapter`
- Standard logging does NOT support keyword arguments → must use `extra={}`
- Has built-in Temporal features like replay log suppression

**Activities and Services (`structlog`)**

- Run outside the workflow sandbox (normal Python environment)
- structlog's keyword argument syntax (`key=value`) works directly
- OpenTelemetry trace context is automatically injected

### Code Examples

```python
# Workflow (inside sandbox) - use extra={}
@workflow.defn
class MyWorkflow:
    @workflow.run
    async def run(self, input: MyInput) -> MyResult:
        workflow.logger.info(
            "Processing started",
            extra={"workflow_id": workflow.info().workflow_id, "count": 10},
        )

# Activity (outside sandbox) - use keyword arguments
import logging
logger = logging.getLogger(__name__)

@activity.defn
async def my_activity(input: MyInput) -> MyResult:
    logger.info("Processing entry", entry_id=input.entry_id, count=10)
```

### JSON Output

Both styles produce the same JSON output thanks to the `ExtraAdder` processor:

```json
{
  "event": "Processing started",
  "workflow_id": "wf-123",
  "count": 10,
  "level": "info",
  "component": "worker",
  "timestamp": "2026-01-16T06:00:00.000000Z"
}
```

The `ExtraAdder` processor (configured in `buun_curator/logging.py`) extracts fields from
the `extra` dict and flattens them into the log output.

## Implementation Details

### Frontend (lib/logger.ts)

Uses pino with custom formatters:

```typescript
export const logger = pino({
  level: process.env.LOG_LEVEL || "info",
  messageKey: "event",  // Use "event" instead of "msg"
  formatters: {
    level: (label) => ({ level: label }),
  },
  timestamp: () => `,"timestamp":"${new Date().toISOString()}"`,
  mixin: getTraceContext,  // Adds component, trace_id, span_id
});
```

### Worker (buun_curator/logging.py)

Uses structlog with custom processors:

```python
shared_processors = [
    structlog.contextvars.merge_contextvars,
    structlog.stdlib.add_log_level,
    structlog.stdlib.add_logger_name,
    structlog.processors.TimeStamper(fmt="iso"),
    add_trace_context,       # Adds trace_id, span_id
    add_component("worker"), # Adds component field
]
```

### Agent (buun_curator_agent/logging.py)

Same structlog configuration as Worker with `component="agent"`.
