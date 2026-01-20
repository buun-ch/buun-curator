# LLM Evaluation with RAGAS

This document describes the LLM response evaluation system using RAGAS metrics
and Langfuse score recording.

## Overview

The evaluation system measures the quality of AI-generated responses in dialogue
and research modes using [RAGAS](https://docs.ragas.io/) (Retrieval Augmented
Generation Assessment) metrics. Scores are recorded to
[Langfuse](https://langfuse.com/) for observability and quality tracking.

## Architecture

```text
┌─────────────────┐     start_workflow      ┌──────────────────┐
│  Agent Service  │ ──────────────────────► │  Temporal Server │
│  (dialogue.py,  │   (fire-and-forget)     │                  │
│   research.py)  │                         └────────┬─────────┘
└─────────────────┘                                  │
                                                     │ Execute
                                                     ▼
                                            ┌──────────────────┐
                                            │  Worker          │
                                            │  evaluate_ragas  │
                                            │  Activity        │
                                            └────────┬─────────┘
                                                     │
                                     ┌───────────────┼───────────────┐
                                     │               │               │
                                     ▼               ▼               ▼
                              ┌───────────┐  ┌───────────┐  ┌───────────┐
                              │ RAGAS LLM │  │ Embedding │  │ Langfuse  │
                              │ Evaluation│  │ (local)   │  │ Score API │
                              └───────────┘  └───────────┘  └───────────┘
```

**Key design decisions:**

- **Worker-based execution**: Evaluation runs on Worker via Temporal Workflow,
  not in Agent. This keeps Agent lightweight and leverages Temporal's retry
  mechanism.
- **Fire-and-forget**: Agent starts the workflow without waiting, so response
  latency is unaffected.
- **Local embeddings**: Uses sentence-transformers locally instead of OpenAI
  embeddings to reduce costs.

## Metrics

| Metric             | Description                                                                                  | Range     |
| ------------------ | -------------------------------------------------------------------------------------------- | --------- |
| `faithfulness`     | Measures factual consistency of the answer with retrieved contexts (hallucination detection) | 0.0 - 1.0 |
| `answer_relevancy` | Measures how well the answer addresses the user's question                                   | 0.0 - 1.0 |

## Components

### Agent (Trigger)

The Agent triggers evaluation after generating a response:

| File                                          | Purpose                                |
| --------------------------------------------- | -------------------------------------- |
| `agent/buun_curator_agent/temporal.py`        | `start_evaluation_workflow()` function |
| `agent/buun_curator_agent/agents/dialogue.py` | Triggers evaluation in dialogue mode   |
| `agent/buun_curator_agent/agents/research.py` | Triggers evaluation in research mode   |

### Worker (Execution)

The Worker executes RAGAS evaluation and records scores:

| File                                                    | Purpose                                                 |
| ------------------------------------------------------- | ------------------------------------------------------- |
| `worker/buun_curator/workflows/evaluation.py`           | `EvaluationWorkflow`, `SummarizationEvaluationWorkflow` |
| `worker/buun_curator/workflows/content_distillation.py` | Starts `SummarizationEvaluationWorkflow` as child       |
| `worker/buun_curator/activities/evaluation.py`          | `evaluate_ragas`, `evaluate_summarization` activities   |
| `worker/buun_curator/services/evaluation.py`            | RAGAS scoring and Langfuse integration                  |

## Configuration

### Environment Variables

| Variable                     | Description                                | Component |
| ---------------------------- | ------------------------------------------ | --------- |
| `AI_EVALUATION_ENABLED`      | Enable/disable evaluation (`true`/`false`) | Agent     |
| `EVALUATION_EMBEDDING_MODEL` | Embedding model for RAGAS                  | Worker    |
| `LANGFUSE_PUBLIC_KEY`        | Langfuse public key                        | Worker    |
| `LANGFUSE_SECRET_KEY`        | Langfuse secret key                        | Worker    |
| `LANGFUSE_HOST`              | Langfuse host URL                          | Worker    |

### Helm Configuration

```yaml
# values.yaml
evaluation:
  enabled: false
  embeddingModel: sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2

langfuse:
  host: ""
  publicKey: ""
  secretKey: ""
```

## Workflows

### EvaluationWorkflow

Evaluates agent responses (dialogue/research mode).

#### Input

| Field      | Type         | Description                               |
| ---------- | ------------ | ----------------------------------------- |
| `trace_id` | string       | Langfuse trace ID to attach scores to     |
| `mode`     | string       | Agent mode (`"dialogue"` or `"research"`) |
| `question` | string       | User's question                           |
| `contexts` | list[string] | Retrieved context documents               |
| `answer`   | string       | Generated answer                          |

### SummarizationEvaluationWorkflow

Evaluates content summarization quality from ContentDistillationWorkflow.

#### Architecture

```text
┌─────────────────┐     fire-and-forget     ┌──────────────────┐
│  Content        │ ──────────────────────► │  Temporal Server │
│  Distillation   │   (child workflow)      │                  │
│  Workflow       │                         └────────┬─────────┘
└─────────────────┘                                  │
                                                     │ Execute
                                                     ▼
                                            ┌──────────────────┐
                                            │  Summarization   │
                                            │  Evaluation      │
                                            │  Workflow        │
                                            └────────┬─────────┘
                                                     │
                                     ┌───────────────┼───────────────┐
                                     │               │               │
                                     ▼               ▼               ▼
                              ┌───────────┐  ┌───────────┐  ┌───────────┐
                              │ RAGAS LLM │  │ Embedding │  │ Langfuse  │
                              │ Evaluation│  │ (local)   │  │ Score API │
                              └───────────┘  └───────────┘  └───────────┘
```

**Key design:**

- **Fire-and-forget child workflow**: Launched with `ParentClosePolicy.ABANDON` so
  parent workflow completes immediately without waiting for evaluation.
- **Sampling**: Evaluates up to `max_samples` (default: 5) summaries to control costs.
- **Per-entry traces**: Each entry gets a separate trace (`distillation-eval`)
  with individual scores. Entry ID is stored in metadata.
- **Batch average scores**: Recorded as `batch_faithfulness` and `batch_answer_relevancy`
  on the batch trace (`distillation-batch`).

#### Input

| Field         | Type                              | Description                                      |
| ------------- | --------------------------------- | ------------------------------------------------ |
| `trace_id`    | string                            | Langfuse trace ID from distillation              |
| `items`       | list[SummarizationEvaluationItem] | Items to evaluate                                |
| `max_samples` | int                               | Maximum number of items to evaluate (default: 5) |

**SummarizationEvaluationItem:**

| Field              | Type   | Description                                |
| ------------------ | ------ | ------------------------------------------ |
| `entry_id`         | string | Entry identifier                           |
| `original_content` | string | Original content before summarization      |
| `summary`          | string | Generated summary                          |
| `trace_id`         | string | Per-entry trace ID for Langfuse (optional) |

#### Metrics

**Per-entry scores** (on `distillation-eval` trace):

| Metric             | Description                                                      |
| ------------------ | ---------------------------------------------------------------- |
| `faithfulness`     | Whether summary is factually consistent with original            |
| `answer_relevancy` | Whether summary appropriately addresses "Summarize this content" |

**Batch average scores** (on `distillation-batch` trace):

| Metric                   | Description                                                  |
| ------------------------ | ------------------------------------------------------------ |
| `batch_faithfulness`     | Arithmetic mean of faithfulness across evaluated entries     |
| `batch_answer_relevancy` | Arithmetic mean of answer_relevancy across evaluated entries |

### Error Handling

The activity raises exceptions on failure (does not catch and return
`success=False`). This ensures:

1. Temporal applies retry policy (2 attempts, 5 second interval)
2. Workflow is marked as **Failed** after retries are exhausted
3. Errors are visible in Temporal UI for debugging

### Viewing Results

Scores are recorded to Langfuse traces. To view:

**Agent evaluation (dialogue/research):**

1. Open Langfuse dashboard
2. Find the trace by `trace_id` (32-char hex format)
3. View attached scores (`faithfulness`, `answer_relevancy`)

**Summarization evaluation:**

1. Open Langfuse dashboard
2. Find traces by name:
   - `distillation-batch`: Batch LLM calls + average scores
   - `distillation-eval`: Per-entry filtering results + individual scores (entry_id in metadata)
3. View attached scores

## Research Agent Batch Evaluation

In addition to real-time evaluation during agent responses, batch evaluation
allows systematic testing of the Research Agent across multiple queries with
different search modes.

### Workflow

```text
┌─────────────────────────────────────────────────────────────────────────────┐
│                           Batch Evaluation Workflow                          │
└─────────────────────────────────────────────────────────────────────────────┘

  Step 1: Generate Dataset              Step 2: Run Evaluation
  (Worker)                              (Agent)

  ┌─────────────────────┐               ┌─────────────────────┐
  │ generate-eval-dataset│               │     batch-eval      │
  └──────────┬──────────┘               └──────────┬──────────┘
             │                                     │
             ▼                                     ▼
  ┌─────────────────────┐               ┌─────────────────────┐
  │ Sample entries from │               │ For each dataset    │
  │ DB (K-means on      │               │ item:               │
  │ embeddings)         │               │  1. Run Research    │
  └──────────┬──────────┘               │     Agent           │
             │                          │  2. Compute RAGAS   │
             ▼                          │     scores          │
  ┌─────────────────────┐               │  3. Record to       │
  │ Generate QA pairs   │               │     Langfuse        │
  │ with RAGAS          │               └──────────┬──────────┘
  │ TestsetGenerator    │                          │
  └──────────┬──────────┘                          ▼
             │                          ┌─────────────────────┐
             ▼                          │ Langfuse Experiment │
  ┌─────────────────────┐               │ - Per-item scores   │
  │ Upload to Langfuse  │──────────────►│ - Run-level avg     │
  │ Dataset             │               │ - Mode comparison   │
  └─────────────────────┘               └─────────────────────┘
```

### Step 1: Generate Evaluation Dataset

Use `generate-eval-dataset` to create QA pairs from database entries:

```bash
cd worker
uv run generate-eval-dataset                   # Generate and upload to Langfuse
uv run generate-eval-dataset --dataset-size 5  # 5 QA samples per pattern
uv run generate-eval-dataset --no-upload       # Skip Langfuse upload
```

**Features:**

- Samples diverse entries using K-means clustering on embeddings
- Generates 4 language patterns: en→en, en→ja, ja→en, ja→ja
- Uses RAGAS TestsetGenerator for QA pair creation
- Uploads to Langfuse Dataset for batch evaluation

**Output:**

```text
evaluation/<dataset-name>/
├── data/
│   ├── eval_targets.json    # Sampled entries
│   └── qa/
│       └── eval_qa.json     # Generated QA pairs
└── results/                 # Evaluation results (from batch-eval)
```

### Step 2: Run Batch Evaluation

Use `batch-eval` to evaluate the Research Agent on the generated dataset:

```bash
cd agent
uv run batch-eval                              # Run with default dataset
uv run batch-eval --mode embedding             # Use embedding search only
uv run batch-eval --all-modes                  # Compare all search modes
uv run batch-eval --limit 5 --dry-run          # Preview 5 items
```

**Search modes:**

| Mode          | Description                                              |
| ------------- | -------------------------------------------------------- |
| `planner`     | Planner selects optimal sources based on query (default) |
| `meilisearch` | Full-text search only                                    |
| `embedding`   | Vector search only                                       |
| `hybrid`      | Both sources, merged results                             |

**Results:**

- JSON files: `../worker/evaluation/<dataset-name>/results/<date>-<mode>-<seq>.json`
- Langfuse per-item scores: `faithfulness`, `answer_relevancy`
- Langfuse run-level scores: `avg_faithfulness`, `avg_answer_relevancy`

### Comparing Search Modes

Run `--all-modes` to evaluate all search modes and compare results:

```bash
cd agent
uv run batch-eval --all-modes
```

This runs evaluation for each mode sequentially and outputs a comparison summary:

```text
Mode Comparison Summary
============================================================
  planner: faithfulness=0.8234, answer_relevancy=0.7891
  meilisearch: faithfulness=0.7856, answer_relevancy=0.7234
  embedding: faithfulness=0.8012, answer_relevancy=0.8123
  hybrid: faithfulness=0.8345, answer_relevancy=0.8045
============================================================
```

Results are also available in Langfuse for detailed analysis and visualization.

## Related Documentation

- [Temporal Workflows - EvaluationWorkflow](./workflow.md#evaluationworkflow)
- [RAGAS Documentation](https://docs.ragas.io/)
- [Langfuse Scores](https://langfuse.com/docs/scores)
