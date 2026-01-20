# Development Guide

This guide covers the standard development workflow for Buun Curator using Kubernetes.

## Prerequisites

- [Kubernetes](https://kubernetes.io/) cluster (local or remote)
- [mise](https://mise.jdx.dev/) for tool version management
- [Telepresence](https://www.telepresence.io/) for accessing cluster services
- Container registry accessible from your cluster

### Installing Development Tools

Development tools are managed with [mise](https://mise.jdx.dev/). Install all required tools:

```bash
mise trust
mise install
```

This installs the following tools with pinned versions (see `mise.toml`):

- Bun
- Python, uv
- Helm
- Tilt
- Lefthook
- markdownlint-cli2

Telepresence is not managed by mise because if you use it in other projects, the version of the agent may conflict.

### Setting Up Git Hooks

This project uses [Lefthook](https://github.com/evilmartians/lefthook) for git hooks.
After cloning the repository, install the hooks:

```bash
lefthook install
```

**pre-commit** (runs on staged files):

| Files               | Tools                                  |
| ------------------- | -------------------------------------- |
| `*.md`              | markdownlint-cli2                      |
| `*.{ts,tsx,js,jsx}` | Prettier → ESLint                      |
| `worker/**/*.py`    | Ruff (organize imports → fix → format) |
| `agent/**/*.py`     | Ruff (organize imports → fix → format) |

**pre-push** (runs on push files):

| Files               | Tools               |
| ------------------- | ------------------- |
| `*.{ts,tsx,js,jsx}` | `bun test:unit:run` |
| `worker/**/*.py`    | `uv run pytest`     |
| `agent/**/*.py`     | `uv run pytest`     |

To run the hooks manually:

```bash
# Run pre-commit on staged files
lefthook run pre-commit

# Run pre-commit on all files
lefthook run pre-commit --all-files

# Run pre-push
lefthook run pre-push

# Skip hooks when needed
git push --no-verify
```

### Recommended: buun-stack

For the easiest setup, use [buun-stack](https://github.com/buun-ch/buun-stack) which provides
a pre-configured Kubernetes environment with all required services:

- PostgreSQL (CloudNativePG)
- Temporal
- Meilisearch
- MinIO
- LiteLLM
- Keycloak
- Langfuse

## Quick Start

### 1. Set Up Secrets

Create a Kubernetes Secret with your credentials in the `buun-curator` namespace:

```bash
kubectl create namespace buun-curator

kubectl create secret generic buun-curator-secret \
  --namespace buun-curator \
  --from-literal=OPENAI_API_KEY="sk-..." \
  --from-literal=S3_ACCESS_KEY="minioadmin" \
  --from-literal=S3_SECRET_KEY="minioadmin" \
  --from-literal=MEILISEARCH_API_KEY="your-key" \
  --from-literal=INTERNAL_API_TOKEN="your-token" \
  --from-literal=BETTER_AUTH_SECRET="$(openssl rand -base64 32)"
```

See [Helm Chart README](../charts/buun-curator/README.md#using-existing-secrets) for the full
list of environment variables that can be set via Secret.

### 2. Start Development Environment

```bash
tilt up --namespace buun-curator
```

This deploys the Helm chart using `charts/buun-curator/values-dev.yaml` with:

- Hot reload enabled for all components (frontend, worker, agent)
- Debug logging
- Development-friendly probe settings

### 3. Connect to Cluster Services

```bash
telepresence connect
```

Access the application at: <http://buun-curator.buun-curator:3000>

## Tilt Configuration

### Basic Usage

```bash
# Start development environment
tilt up

# Start with namespace override
tilt up --namespace buun-curator

# Stop and clean up
tilt down
```

### Configuration Options

Tilt supports several configuration flags:

| Flag                   | Description                              | Default           |
| ---------------------- | ---------------------------------------- | ----------------- |
| `--registry`           | Container registry URL                   | `localhost:30500` |
| `--port-forward`       | Enable port forwarding (localhost:13000) | `false`           |
| `--extra-values-file`  | Additional Helm values file              | -                 |
| `--enable-health-logs` | Enable health check request logging      | `false`           |
| `--prod-image`         | Use production Dockerfile instead of dev | `false`           |

Examples:

```bash
# With port forwarding (useful without Telepresence)
tilt up -- --port-forward

# With additional values file
tilt up -- --extra-values-file=./my-values.yaml

# Build production images
tilt up -- --prod-image
```

### Live Reload

Development mode enables live reload for all components:

- **Frontend**: File changes sync to container, `bun install` runs on package.json changes
- **Worker**: File changes sync to container, `uv sync` runs on pyproject.toml changes
- **Agent**: File changes sync to container, `uv sync` runs on pyproject.toml changes

## Secrets Management

### Option 1: Manual Secret Creation

Create secrets directly with kubectl as shown in Quick Start.

### Option 2: External Secrets Operator

If you use [External Secrets Operator](https://external-secrets.io/), you can use
`manifests/buun-curator-external-secret.yaml` as a template:

```bash
kubectl apply -f manifests/buun-curator-external-secret.yaml -n buun-curator
```

This creates a `buun-curator-secret` Secret from your external secret store (e.g., HashiCorp
Vault, AWS Secrets Manager).

The ExternalSecret maps the following secrets:

| Secret Store Key            | Environment Variable                                                              |
| --------------------------- | --------------------------------------------------------------------------------- |
| `buun-curator/s3`           | `S3_ACCESS_KEY`, `S3_SECRET_KEY`                                                  |
| `buun-curator/deep_l`       | `DEEPL_API_KEY`                                                                   |
| `buun-curator/microsoft`    | `MS_TRANSLATOR_SUBSCRIPTION_KEY`, `MS_TRANSLATOR_REGION`                          |
| `buun-curator/litellm`      | `OPENAI_API_KEY`                                                                  |
| `buun-curator/langfuse`     | `LANGFUSE_PUBLIC_KEY`, `LANGFUSE_SECRET_KEY`                                      |
| `buun-curator/keycloak`     | `KEYCLOAK_URL`, `KEYCLOAK_CLIENT_ID`, `KEYCLOAK_CLIENT_SECRET`, `BETTER_AUTH_URL` |
| `buun-curator/internal-api` | `INTERNAL_API_TOKEN`                                                              |
| `buun-curator/better-auth`  | `BETTER_AUTH_SECRET`                                                              |
| `buun-curator/github`       | `GITHUB_TOKEN`                                                                    |
| `buun-curator/meilisearch`  | `MEILISEARCH_API_KEY`                                                             |

## Development Values

The `charts/buun-curator/values-dev.yaml` file contains development-specific configuration:

```yaml
frontend:
  serverUrl: http://buun-curator.buun-curator:3000
  allowedDevOrigins: buun-curator.buun-curator
  extraEnvVarsSecret: buun-curator-secret

worker:
  reload: true
  logLevel: debug
  extraEnvVarsSecret: buun-curator-secret

agent:
  reload: true
  logLevel: debug
  extraEnvVarsSecret: buun-curator-secret
```

Key differences from production:

- `reload: true` enables auto-reload on code changes
- `logLevel: debug` for verbose logging
- Longer probe timeouts for JIT compilation during development
- `migration.enabled: false` (run migrations manually or via CI/CD)

## Common Tasks

### Run Database Migrations

```bash
# From your local machine
bun db:migrate

# Or connect to the cluster and run from there
telepresence connect
DATABASE_URL="postgresql://buun_curator:buun_curator@postgres-cluster-rw.postgres:5432/buun_curator_dev" \
  bun db:migrate
```

### Trigger Feed Ingestion

```bash
cd worker
telepresence connect
TEMPORAL_HOST=temporal-frontend.temporal:7233 \
TEMPORAL_NAMESPACE=buun-curator \
  uv run trigger ingest
```

### View Logs

See [Logs and Tracing](./logs-and-tracing.md) for viewing logs in development.

### Rebuild Images

Tilt automatically rebuilds images on file changes. To force a rebuild:

```bash
# In Tilt UI, click the refresh button on the resource
# Or restart Tilt
tilt down && tilt up
```

## Troubleshooting

### Telepresence Connection Issues

```bash
# Check Telepresence status
telepresence status

# Reconnect
telepresence quit
telepresence connect
```

### Pods Not Starting

```bash
# Check pod status
kubectl get pods -n buun-curator

# Check events
kubectl get events -n buun-curator --sort-by='.lastTimestamp'

# Check pod details
kubectl describe pod <pod-name> -n buun-curator
```

### Image Pull Errors

Ensure your container registry is accessible from the cluster:

```bash
# For local registries, check if the registry is running
docker ps | grep registry

# Verify Tilt registry setting
tilt up -- --registry=your-registry:port
```

### Secret Not Found

Verify the secret exists:

```bash
kubectl get secret buun-curator-secret -n buun-curator

# Check secret contents (base64 encoded)
kubectl get secret buun-curator-secret -n buun-curator -o yaml
```
