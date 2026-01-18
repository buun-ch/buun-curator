# Testing

This document covers testing strategies for Buun Curator, with a focus on E2E testing
for SSE (Server-Sent Events) connection resilience.

## Test Types

| Type | Framework              | Location       | Purpose                   |
| ---- | ---------------------- | -------------- | ------------------------- |
| Unit | Vitest                 | `tests/unit/`  | Logic testing             |
| E2E  | Playwright + Toxiproxy | `tests/e2e/`   | SSE connection resilience |

## Setup

Create a test database `buun_curator_test` and run migrations:

```bash
bun db:migrate:test
```

## Unit Tests

Unit tests use Vitest and run in Node.js environment.

```bash
# Run all unit tests
bun test:unit:run

# Run tests in watch mode
bun test:unit

# Run specific test file
bun vitest run tests/unit/sse-keepalive.test.ts
```

> **Note**: Use `bun test:unit` instead of `bun test`. The latter invokes Bun's
> built-in test runner, which is incompatible with Vitest APIs.

### SSE Keep-alive Tests

`tests/unit/sse-keepalive.test.ts` tests the timeout detection logic:

- Timeout threshold detection (45 seconds)
- Visibility change handling
- Reconnection scenarios

## E2E Tests

E2E tests verify SSE connection behavior under network fault conditions using:

- **Playwright**: Browser automation
- **Toxiproxy**: Network fault injection (TCP proxy)

### Architecture

```text
┌─────────────────────────────────────────────────────────────────┐
│                    Namespace: buun-curator-e2e                  │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  ┌───────────┐     ┌─────────────┐     ┌──────────────────┐    │
│  │ Playwright│────▶│  Toxiproxy  │────▶│     Frontend     │    │
│  │ (CI only) │     │   :8080     │     │      :3000       │    │
│  └───────────┘     └─────────────┘     └──────────────────┘    │
│        ▲                 │                                      │
│        │          Network fault                                 │
│        │          injection here                                │
│        │                                                        │
│  ┌─────┴─────┐    Toxiproxy API: :8474                         │
│  │  Local    │                                                  │
│  │ Playwright│ (via Telepresence)                              │
│  └───────────┘                                                  │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

**Local testing**: Playwright runs on local machine via Telepresence.
**CI testing**: Playwright runs in the cluster pod.

### Build Mode

E2E tests use **production Docker images** (not development images):

| Component | Dockerfile          | Mode       |
| --------- | ------------------- | ---------- |
| Frontend  | `Dockerfile`        | Production |
| Worker    | `worker/Dockerfile` | Production |
| Agent     | `agent/Dockerfile`  | Production |

This ensures:

- No rebuilds during test execution
- Tests run against production-like builds
- `NODE_ENV=production` for frontend

### Prerequisites

- Kubernetes cluster with Tilt
- Telepresence (for local test execution)
- Docker registry accessible from cluster

### Setup

#### 1. Create E2E Namespace

```bash
kubectl create namespace buun-curator-e2e
```

#### 2. Copy Secrets (if needed)

```bash
# Copy secrets from dev namespace
kubectl get secret buun-curator-secret -n buun-curator -o yaml | \
  sed 's/namespace: buun-curator/namespace: buun-curator-e2e/' | \
  kubectl apply -f -
```

#### 3. Deploy E2E Environment

```bash
# Start E2E environment (default namespace: buun-curator-e2e)
# Use --port 10351 to run simultaneously with dev Tilt (default port 10350)
tilt up -f Tiltfile.e2e --port 10351

# With custom namespace
tilt up -f Tiltfile.e2e --port 10351 -- --namespace=my-e2e-ns

# With port forwarding (without Telepresence)
tilt up -f Tiltfile.e2e --port 10351 -- --port-forward

# Combine options
tilt up -f Tiltfile.e2e --port 10351 -- --namespace=my-e2e-ns --port-forward
```

#### 4. Connect via Telepresence

```bash
telepresence connect
```

### Running E2E Tests

#### From Local Machine (via Telepresence)

```bash
# Run all E2E tests
bun test:e2e

# Run with UI
bun test:e2e:ui

# Run specific test file
bunx playwright test tests/e2e/sse.test.ts
```

#### From Playwright Container (CI)

The Playwright pod is primarily for CI pipelines. For local development,
use Telepresence instead.

```bash
kubectl exec -it deploy/buun-curator-playwright -n buun-curator-e2e -- \
  npx playwright test
```

### Running Development and E2E Simultaneously

You can run both environments at the same time by using different Tilt ports:

```bash
# Terminal 1: Development (default port 10350)
tilt up

# Terminal 2: E2E Testing (port 10351)
tilt up -f Tiltfile.e2e --port 10351
```

| Environment | Command                                | Tilt Port | Namespace            |
| ----------- | -------------------------------------- | --------- | -------------------- |
| Development | `tilt up`                              | 10350     | `buun-curator`       |
| E2E Testing | `tilt up -f Tiltfile.e2e --port 10351` | 10351     | `buun-curator-e2e`\* |

\* Default namespace. Use `-- --namespace=<name>` to customize.

### Port Forwarding (without Telepresence)

If you prefer not to use Telepresence:

```bash
tilt up -f Tiltfile.e2e -- --port-forward
```

| Service         | Local Port | Description          |
| --------------- | ---------- | -------------------- |
| Frontend        | 13001      | Direct access to app |
| Toxiproxy API   | 18474      | Proxy management API |
| Toxiproxy Proxy | 18080      | Proxied frontend     |

## Toxiproxy Usage

Toxiproxy allows injecting network faults to test connection resilience.

### API Endpoints

| Endpoint                         | Method | Description      |
| -------------------------------- | ------ | ---------------- |
| `/proxies`                       | GET    | List all proxies |
| `/proxies`                       | POST   | Create proxy     |
| `/proxies/{name}`                | DELETE | Delete proxy     |
| `/proxies/{name}/toxics`         | POST   | Add toxic        |
| `/proxies/{name}/toxics/{toxic}` | DELETE | Remove toxic     |

### Creating a Proxy

```bash
TOXIPROXY_API=http://buun-curator-toxiproxy.buun-curator-e2e:8474

# Create proxy: Toxiproxy:8080 → Frontend:3000
curl -X POST $TOXIPROXY_API/proxies \
  -H "Content-Type: application/json" \
  -d '{
    "name": "frontend-sse",
    "listen": "0.0.0.0:8080",
    "upstream": "buun-curator.buun-curator-e2e:3000",
    "enabled": true
  }'
```

### Injecting Faults

#### Timeout (Connection Drop)

Simulates connection loss by dropping all data:

```bash
# Drop all data (simulates sleep/network outage)
curl -X POST $TOXIPROXY_API/proxies/frontend-sse/toxics \
  -H "Content-Type: application/json" \
  -d '{
    "name": "timeout",
    "type": "timeout",
    "stream": "downstream",
    "attributes": {"timeout": 0}
  }'

# Remove toxic to restore connection
curl -X DELETE $TOXIPROXY_API/proxies/frontend-sse/toxics/timeout
```

#### Latency

Adds delay to simulate slow network:

```bash
# Add 5 second latency with 1 second jitter
curl -X POST $TOXIPROXY_API/proxies/frontend-sse/toxics \
  -H "Content-Type: application/json" \
  -d '{
    "name": "latency",
    "type": "latency",
    "stream": "downstream",
    "attributes": {"latency": 5000, "jitter": 1000}
  }'
```

#### Bandwidth Limit

Limits bandwidth to simulate slow connection:

```bash
# Limit to 10 KB/s
curl -X POST $TOXIPROXY_API/proxies/frontend-sse/toxics \
  -H "Content-Type: application/json" \
  -d '{
    "name": "bandwidth",
    "type": "bandwidth",
    "stream": "downstream",
    "attributes": {"rate": 10}
  }'
```

#### Reset Peer (TCP RST)

Simulates TCP connection reset:

```bash
# Reset connection after 5 seconds
curl -X POST $TOXIPROXY_API/proxies/frontend-sse/toxics \
  -H "Content-Type: application/json" \
  -d '{
    "name": "reset_peer",
    "type": "reset_peer",
    "stream": "downstream",
    "attributes": {"timeout": 5000}
  }'
```

### Toxiproxy Client (TypeScript)

The test helper at `tests/e2e/helpers/toxiproxy-client.ts` provides convenient functions:

```typescript
import {
  createProxy,
  deleteProxy,
  addTimeoutToxic,
  addLatencyToxic,
  removeAllToxics,
} from "./helpers/toxiproxy-client";

// Create proxy
await createProxy("frontend-sse", "0.0.0.0:8080", "buun-curator:3000");

// Inject timeout (drops all data)
await addTimeoutToxic("frontend-sse", 0);

// Inject latency
await addLatencyToxic("frontend-sse", 5000, 1000);

// Clean up
await removeAllToxics("frontend-sse");
await deleteProxy("frontend-sse");
```

## SSE Test Scenarios

### Test: Connection Timeout

Tests that the client reconnects after connection loss.

1. Establish SSE connection
2. Inject `timeout` toxic (drops all data)
3. Verify status changes to disconnected/error
4. Remove toxic
5. Verify reconnection

### Test: Visibility Change After Sleep

Tests the sleep/wake detection logic.

1. Establish SSE connection
2. Inject `timeout` toxic
3. Simulate `visibilitychange` to hidden
4. Wait 50+ seconds (past 45s threshold)
5. Remove toxic
6. Simulate `visibilitychange` to visible
7. Verify reconnection triggered

### Test: Latency Spikes

Tests that high latency doesn't break the connection.

1. Establish SSE connection
2. Inject `latency` toxic (5s delay)
3. Verify connection remains stable
4. Remove toxic

### Test: TCP Reset

Tests recovery from sudden connection termination.

1. Establish SSE connection
2. Delete proxy (simulates TCP RST)
3. Verify disconnection detected
4. Recreate proxy
5. Verify reconnection

## Troubleshooting

### Tests Fail to Connect

1. Verify E2E environment is running:

   ```bash
   kubectl get pods -n buun-curator-e2e
   ```

2. Check Telepresence connection:

   ```bash
   telepresence status
   ```

3. Verify proxy is created:

   ```bash
   curl http://buun-curator-toxiproxy.buun-curator-e2e:8474/proxies
   ```

### Toxiproxy API Not Responding

Check the Toxiproxy pod logs:

```bash
kubectl logs deploy/buun-curator-toxiproxy -n buun-curator-e2e
```

### SSE Status Indicator Not Found

The E2E tests rely on `data-testid="sse-status"` attribute on the SSE status indicator
component. Ensure the component is rendered and visible on the page.

## References

- [Toxiproxy GitHub](https://github.com/Shopify/toxiproxy)
- [Playwright Documentation](https://playwright.dev/)
- [Vitest Documentation](https://vitest.dev/)
