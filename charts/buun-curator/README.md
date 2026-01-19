# Buun Curator

Buun Curator is a multi-panel feed reader with integrated AI assistant for curating and summarizing content.

## TL;DR

```console
helm install my-release oci://ghcr.io/yatsu/buun-curator
```

## Introduction

This chart bootstraps a Buun Curator deployment on a [Kubernetes](https://kubernetes.io) cluster using the [Helm](https://helm.sh) package manager.

Buun Curator consists of three components:

- **Frontend**: Next.js web application providing the user interface
- **Worker**: Temporal worker for background processing (feed ingestion, summarization)
- **Agent**: CopilotKit agent service for AI assistant functionality

## Prerequisites

- Kubernetes 1.23+
- Helm 3.8.0+
- PostgreSQL database
- Temporal server
- Meilisearch instance
- OpenAI API key or compatible LLM endpoint
- Keycloak server (optional)

## Installing the Chart

To install the chart with the release name `my-release`:

```console
helm install my-release oci://ghcr.io/yatsu/buun-curator
```

These commands deploy Buun Curator on the Kubernetes cluster with default configuration. The [Parameters](#parameters) section lists the parameters that can be configured during installation.

> **Tip**: List all releases using `helm list`

## Uninstalling the Chart

To uninstall/delete the `my-release` deployment:

```console
helm delete my-release
```

## Configuration and installation details

### Configuring environment variables

This chart supports multiple ways to configure environment variables:

#### Using extraEnvVars

Additional environment variables can be added using the `extraEnvVars` parameter:

```yaml
frontend:
  extraEnvVars:
    - name: CUSTOM_VAR
      value: "custom-value"
```

#### Using existing Secrets

For sensitive data like API keys, use existing Kubernetes Secrets:

```console
kubectl create secret generic buun-curator-secrets \
  --from-literal=OPENAI_API_KEY="sk-..." \
  --from-literal=DATABASE_URL="postgresql://user:pass@host:5432/db"
```

Then reference the secret in your values:

```yaml
frontend:
  extraEnvVarsSecret: "buun-curator-secrets"
worker:
  extraEnvVarsSecret: "buun-curator-secrets"
agent:
  extraEnvVarsSecret: "buun-curator-secrets"
```

The following table shows the mapping between Helm values and environment variables. These can be provided via Secret instead of setting them directly in values.yaml:

| Helm Value                                     | Environment Variable             | Components              | Description                    |
| ---------------------------------------------- | -------------------------------- | ----------------------- | ------------------------------ |
| `postgres.app.*`                               | `DATABASE_URL`                   | Frontend, Worker        | PostgreSQL connection URL      |
| `worker.s3.accessKey`                          | `S3_ACCESS_KEY`                  | Worker                  | S3 access key                  |
| `worker.s3.secretKey`                          | `S3_SECRET_KEY`                  | Worker                  | S3 secret key                  |
| `worker.translation.deepl.apiKey`              | `DEEPL_API_KEY`                  | Worker                  | DeepL API key                  |
| `worker.translation.microsoft.subscriptionKey` | `MS_TRANSLATOR_SUBSCRIPTION_KEY` | Worker                  | Microsoft Translator key       |
| `llm.apiKey`                                   | `OPENAI_API_KEY`                 | Frontend, Worker, Agent | LLM API key                    |
| `langfuse.publicKey`                           | `LANGFUSE_PUBLIC_KEY`            | Worker, Agent           | Langfuse public key            |
| `langfuse.secretKey`                           | `LANGFUSE_SECRET_KEY`            | Worker, Agent           | Langfuse secret key            |
| `auth.clientId`                                | `KEYCLOAK_CLIENT_ID`             | Frontend                | Keycloak client ID             |
| `auth.clientSecret`                            | `KEYCLOAK_CLIENT_SECRET`         | Frontend                | Keycloak client secret         |
| `internalApi.token`                            | `INTERNAL_API_TOKEN`             | Frontend, Worker        | Internal API token             |
| `auth.secret`                                  | `BETTER_AUTH_SECRET`             | Frontend                | Better Auth secret             |
| `research.context.githubToken`                 | `GITHUB_TOKEN`                   | Worker, Agent           | GitHub token for private repos |
| `meilisearch.apiKey`                           | `MEILISEARCH_API_KEY`            | Frontend, Worker        | Meilisearch API key            |

> **Note**: When an environment variable is set via Secret, it takes precedence over the corresponding Helm value.

#### Using existing ConfigMaps

For non-sensitive configuration:

```console
kubectl create configmap buun-curator-config \
  --from-literal=OPENAI_MODEL="gpt-4"
```

Then reference the ConfigMap in your values:

```yaml
frontend:
  extraEnvVarsCM: "buun-curator-config"
```

### Configuring Ingress

To enable Ingress for the frontend:

```yaml
ingress:
  enabled: true
  className: "nginx"
  annotations:
    cert-manager.io/cluster-issuer: "letsencrypt-prod"
  hosts:
    - host: buun-curator.example.com
      paths:
        - path: /
          pathType: Prefix
  tls:
    - secretName: buun-curator-tls
      hosts:
        - buun-curator.example.com
```

### Configuring LLM

Buun Curator requires an LLM for AI features. Configure the LLM endpoint:

```yaml
llm:
  baseUrl: "" # Empty for OpenAI, or set to LiteLLM proxy URL
  apiKey: "sk-..."
  models:
    default: "gpt-4o-mini"
    extraction: "" # Falls back to default if empty
    summarization: ""
    assistant: ""
```

### Configuring S3/MinIO for thumbnails

The worker requires S3-compatible storage for thumbnails:

```yaml
worker:
  s3:
    endpoint: "https://minio.example.com" # Empty for AWS S3
    accessKey: "minioadmin"
    secretKey: "minioadmin"
    bucket: "buun-curator"
    publicUrl: "https://minio.example.com/buun-curator"
    region: "us-east-1"
```

## Parameters

### Common parameters

| Name               | Description                               | Value |
| ------------------ | ----------------------------------------- | ----- |
| `imagePullSecrets` | Docker registry secret names as an array  | `[]`  |
| `nameOverride`     | String to partially override the fullname | `""`  |
| `fullnameOverride` | String to fully override the fullname     | `""`  |

### Frontend parameters

| Name                                                  | Description                                                       | Value                   |
| ----------------------------------------------------- | ----------------------------------------------------------------- | ----------------------- |
| `frontend.enabled`                                    | Enable frontend deployment                                        | `true`                  |
| `frontend.replicaCount`                               | Number of frontend replicas                                       | `1`                     |
| `frontend.image.imageRegistry`                        | Frontend image registry                                           | `""`                    |
| `frontend.image.repository`                           | Frontend image repository                                         | `buun-curator-frontend` |
| `frontend.image.tag`                                  | Frontend image tag (defaults to chart appVersion)                 | `latest`                |
| `frontend.image.pullPolicy`                           | Frontend image pull policy                                        | `IfNotPresent`          |
| `frontend.podAnnotations`                             | Annotations for frontend pods                                     | `{}`                    |
| `frontend.podLabels`                                  | Labels for frontend pods                                          | `{}`                    |
| `frontend.podSecurityContext`                         | Security context for frontend pods                                | `{}`                    |
| `frontend.securityContext`                            | Security context for frontend containers                          | `{}`                    |
| `frontend.service.type`                               | Frontend service type                                             | `ClusterIP`             |
| `frontend.service.port`                               | Frontend service port                                             | `3000`                  |
| `frontend.resources`                                  | Resource requests/limits for frontend containers                  | `{}`                    |
| `frontend.startupProbe`                               | Startup probe configuration                                       | See values.yaml         |
| `frontend.livenessProbe`                              | Liveness probe configuration                                      | See values.yaml         |
| `frontend.readinessProbe`                             | Readiness probe configuration                                     | See values.yaml         |
| `frontend.autoscaling.enabled`                        | Enable autoscaling for frontend                                   | `false`                 |
| `frontend.autoscaling.minReplicas`                    | Minimum number of replicas                                        | `1`                     |
| `frontend.autoscaling.maxReplicas`                    | Maximum number of replicas                                        | `100`                   |
| `frontend.autoscaling.targetCPUUtilizationPercentage` | Target CPU utilization percentage                                 | `80`                    |
| `frontend.volumes`                                    | Additional volumes for frontend pods                              | `[]`                    |
| `frontend.volumeMounts`                               | Additional volume mounts for frontend containers                  | `[]`                    |
| `frontend.nodeSelector`                               | Node selector for frontend pods                                   | `{}`                    |
| `frontend.tolerations`                                | Tolerations for frontend pods                                     | `[]`                    |
| `frontend.affinity`                                   | Affinity for frontend pods                                        | `{}`                    |
| `frontend.telemetry.enabled`                          | Enable telemetry                                                  | `false`                 |
| `frontend.logging.health_request`                     | Enable health check request logging                               | `false`                 |
| `frontend.agentUrl`                                   | Agent URL for CopilotKit                                          | `""`                    |
| `frontend.allowedDevOrigins`                          | Allowed dev origins for CORS                                      | `""`                    |
| `frontend.env`                                        | Environment variables for frontend containers                     | `[]`                    |
| `frontend.envFrom`                                    | Environment variables from ConfigMaps or Secrets                  | `[]`                    |
| `frontend.extraEnvVars`                               | Extra environment variables as key-value pairs                    | `[]`                    |
| `frontend.extraEnvVarsSecret`                         | Name of existing Secret containing extra environment variables    | `""`                    |
| `frontend.extraEnvVarsCM`                             | Name of existing ConfigMap containing extra environment variables | `""`                    |
| `frontend.initContainers`                             | Init containers to run before the main container                  | `[]`                    |

### Worker parameters

| Name                                           | Description                                                       | Value                 |
| ---------------------------------------------- | ----------------------------------------------------------------- | --------------------- |
| `worker.reload`                                | Enable auto-reload on code changes (for development)              | `false`               |
| `worker.replicaCount`                          | Number of worker replicas                                         | `2`                   |
| `worker.image.imageRegistry`                   | Worker image registry                                             | `""`                  |
| `worker.image.repository`                      | Worker image repository                                           | `buun-curator-worker` |
| `worker.image.tag`                             | Worker image tag                                                  | `latest`              |
| `worker.image.pullPolicy`                      | Worker image pull policy                                          | `IfNotPresent`        |
| `worker.podAnnotations`                        | Annotations for worker pods                                       | `{}`                  |
| `worker.podLabels`                             | Labels for worker pods                                            | `{}`                  |
| `worker.podSecurityContext`                    | Security context for worker pods                                  | `{}`                  |
| `worker.securityContext`                       | Security context for worker containers                            | `{}`                  |
| `worker.resources`                             | Resource requests/limits for worker containers                    | `{}`                  |
| `worker.apiUrl`                                | API URL for REST API access                                       | `""`                  |
| `worker.logLevel`                              | Log level for worker                                              | `info`                |
| `worker.feedIngestionConcurrency`              | Feed ingestion concurrency                                        | `5`                   |
| `worker.maxEntryAgeDays`                       | Max entry age in days (0 = no limit)                              | `7`                   |
| `worker.concurrency.maxActivities`             | Max concurrent activity tasks                                     | `10`                  |
| `worker.concurrency.maxWorkflowTasks`          | Max concurrent workflow tasks                                     | `10`                  |
| `worker.concurrency.maxLocalActivities`        | Max concurrent local activities (0 = Temporal default)            | `0`                   |
| `worker.s3.endpoint`                           | S3 endpoint (empty for AWS S3)                                    | `""`                  |
| `worker.s3.accessKey`                          | S3 access key                                                     | `""`                  |
| `worker.s3.secretKey`                          | S3 secret key                                                     | `""`                  |
| `worker.s3.bucket`                             | S3 bucket name                                                    | `buun-curator`        |
| `worker.s3.prefix`                             | S3 key prefix                                                     | `""`                  |
| `worker.s3.publicUrl`                          | S3 public URL                                                     | `""`                  |
| `worker.s3.region`                             | S3 region                                                         | `us-east-1`           |
| `worker.translation.provider`                  | Translation provider (microsoft or deepl)                         | `microsoft`           |
| `worker.translation.microsoft.subscriptionKey` | Microsoft Translator subscription key                             | `""`                  |
| `worker.translation.microsoft.region`          | Microsoft Translator region                                       | `""`                  |
| `worker.translation.deepl.apiKey`              | DeepL API key                                                     | `""`                  |
| `worker.env`                                   | Environment variables for worker containers                       | `[]`                  |
| `worker.envFrom`                               | Environment variables from ConfigMaps or Secrets                  | `[]`                  |
| `worker.extraEnvVars`                          | Extra environment variables as key-value pairs                    | `[]`                  |
| `worker.extraEnvVarsSecret`                    | Name of existing Secret containing extra environment variables    | `""`                  |
| `worker.extraEnvVarsCM`                        | Name of existing ConfigMap containing extra environment variables | `""`                  |
| `worker.volumes`                               | Additional volumes for worker pods                                | `[]`                  |
| `worker.volumeMounts`                          | Additional volume mounts for worker containers                    | `[]`                  |
| `worker.nodeSelector`                          | Node selector for worker pods                                     | `{}`                  |
| `worker.tolerations`                           | Tolerations for worker pods                                       | `[]`                  |
| `worker.affinity`                              | Affinity for worker pods                                          | `{}`                  |
| `worker.healthPort`                            | Health check port                                                 | `8080`                |
| `worker.livenessProbe`                         | Liveness probe configuration                                      | See values.yaml       |
| `worker.readinessProbe`                        | Readiness probe configuration                                     | See values.yaml       |

### Agent parameters

| Name                        | Description                                                       | Value                |
| --------------------------- | ----------------------------------------------------------------- | -------------------- |
| `agent.reload`              | Enable auto-reload on code changes (for development)              | `false`              |
| `agent.replicaCount`        | Number of agent replicas                                          | `1`                  |
| `agent.image.imageRegistry` | Agent image registry                                              | `""`                 |
| `agent.image.repository`    | Agent image repository                                            | `buun-curator-agent` |
| `agent.image.tag`           | Agent image tag                                                   | `latest`             |
| `agent.image.pullPolicy`    | Agent image pull policy                                           | `IfNotPresent`       |
| `agent.podAnnotations`      | Annotations for agent pods                                        | `{}`                 |
| `agent.podLabels`           | Labels for agent pods                                             | `{}`                 |
| `agent.podSecurityContext`  | Security context for agent pods                                   | `{}`                 |
| `agent.securityContext`     | Security context for agent containers                             | `{}`                 |
| `agent.service.type`        | Agent service type                                                | `ClusterIP`          |
| `agent.service.port`        | Agent service port                                                | `8000`               |
| `agent.resources`           | Resource requests/limits for agent containers                     | `{}`                 |
| `agent.livenessProbe`       | Liveness probe configuration                                      | See values.yaml      |
| `agent.readinessProbe`      | Readiness probe configuration                                     | See values.yaml      |
| `agent.logLevel`            | Log level for agent                                               | `info`               |
| `agent.apiBaseUrl`          | API base URL for Next.js API                                      | `""`                 |
| `agent.corsOrigins`         | CORS origins (comma-separated or list)                            | `[]`                 |
| `agent.env`                 | Environment variables for agent containers                        | `[]`                 |
| `agent.envFrom`             | Environment variables from ConfigMaps or Secrets                  | `[]`                 |
| `agent.extraEnvVars`        | Extra environment variables as key-value pairs                    | `[]`                 |
| `agent.extraEnvVarsSecret`  | Name of existing Secret containing extra environment variables    | `""`                 |
| `agent.extraEnvVarsCM`      | Name of existing ConfigMap containing extra environment variables | `""`                 |
| `agent.volumes`             | Additional volumes for agent pods                                 | `[]`                 |
| `agent.volumeMounts`        | Additional volume mounts for agent containers                     | `[]`                 |
| `agent.nodeSelector`        | Node selector for agent pods                                      | `{}`                 |
| `agent.tolerations`         | Tolerations for agent pods                                        | `[]`                 |
| `agent.affinity`            | Affinity for agent pods                                           | `{}`                 |

### Migration parameters

| Name                  | Description                                   | Value  |
| --------------------- | --------------------------------------------- | ------ |
| `migration.enabled`   | Enable database migration (runs as Helm hook) | `true` |
| `migration.resources` | Resource requests/limits for migration job    | `{}`   |

### Service account parameters

| Name                         | Description                                             | Value  |
| ---------------------------- | ------------------------------------------------------- | ------ |
| `serviceAccount.create`      | Specifies whether a service account should be created   | `true` |
| `serviceAccount.automount`   | Automatically mount ServiceAccount's API credentials    | `true` |
| `serviceAccount.annotations` | Annotations to add to the service account               | `{}`   |
| `serviceAccount.name`        | Name of the service account (auto-generated if not set) | `""`   |

### Ingress parameters

| Name                  | Description                 | Value   |
| --------------------- | --------------------------- | ------- |
| `ingress.enabled`     | Enable Ingress for frontend | `false` |
| `ingress.className`   | Ingress class name          | `""`    |
| `ingress.annotations` | Annotations for Ingress     | `{}`    |
| `ingress.hosts`       | Ingress hosts configuration | `[]`    |
| `ingress.tls`         | Ingress TLS configuration   | `[]`    |

### Authentication parameters

| Name           | Description           | Value   |
| -------------- | --------------------- | ------- |
| `auth.enabled` | Enable authentication | `false` |
| `auth.authUrl` | Authentication URL    | `""`    |
| `auth.realm`   | Authentication realm  | `""`    |
| `auth.appUrl`  | Application URL       | `""`    |
| `auth.secret`  | Authentication secret | `""`    |

### Internal API parameters

| Name                | Description        | Value |
| ------------------- | ------------------ | ----- |
| `internalApi.token` | Internal API token | `""`  |

### PostgreSQL parameters

| Name                    | Description              | Value  |
| ----------------------- | ------------------------ | ------ |
| `postgres.app.host`     | PostgreSQL host          | `""`   |
| `postgres.app.port`     | PostgreSQL port          | `5432` |
| `postgres.app.username` | PostgreSQL username      | `""`   |
| `postgres.app.password` | PostgreSQL password      | `""`   |
| `postgres.app.database` | PostgreSQL database name | `""`   |

### Temporal parameters

| Name                 | Description              | Value          |
| -------------------- | ------------------------ | -------------- |
| `temporal.host`      | Temporal server host     | `""`           |
| `temporal.namespace` | Temporal namespace       | `default`      |
| `temporal.taskQueue` | Temporal task queue name | `buun-curator` |

### Meilisearch parameters

| Name                 | Description            | Value          |
| -------------------- | ---------------------- | -------------- |
| `meilisearch.host`   | Meilisearch host       | `""`           |
| `meilisearch.index`  | Meilisearch index name | `buun-curator` |
| `meilisearch.apiKey` | Meilisearch API key    | `""`           |

### LLM parameters

| Name                        | Description                                             | Value        |
| --------------------------- | ------------------------------------------------------- | ------------ |
| `llm.baseUrl`               | LLM base URL (empty for OpenAI, or LiteLLM proxy URL)   | `""`         |
| `llm.apiKey`                | LLM API key                                             | `""`         |
| `llm.models.default`        | Default model for all tasks                             | `gpt-5-mini` |
| `llm.models.extraction`     | Model for extraction tasks (requires Structured Output) | `""`         |
| `llm.models.reasoning`      | Model for reasoning tasks (requires Structured Output)  | `""`         |
| `llm.models.summarization`  | Model for summarization tasks                           | `""`         |
| `llm.models.assistant`      | Model for frontend AI assistant                         | `""`         |
| `llm.models.graphRAG`       | Model for GraphRAG operations                           | `""`         |
| `llm.models.agent.research` | Model for agent research tasks                          | `""`         |

### Evaluation parameters

| Name                        | Description                    | Value                                                         |
| --------------------------- | ------------------------------ | ------------------------------------------------------------- |
| `evaluation.enabled`        | Enable RAGAS evaluation        | `false`                                                       |
| `evaluation.embeddingModel` | Embedding model for evaluation | `sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2` |

### Langfuse parameters

| Name                 | Description         | Value |
| -------------------- | ------------------- | ----- |
| `langfuse.host`      | Langfuse host       | `""`  |
| `langfuse.publicKey` | Langfuse public key | `""`  |
| `langfuse.secretKey` | Langfuse secret key | `""`  |

### Research parameters

| Name                           | Description                                       | Value   |
| ------------------------------ | ------------------------------------------------- | ------- |
| `research.context.enabled`     | Enable research context extraction (experimental) | `false` |
| `research.context.githubToken` | GitHub token for private repository access        | `""`    |
