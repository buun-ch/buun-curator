"""
Batch evaluation script for Research Agent using Langfuse Experiments.

Run RAGAS evaluation on all items in a Langfuse Dataset and record results
as a Langfuse Experiment.

Required Environment Variables
------------------------------
OPENAI_API_KEY : str
    API key for OpenAI-compatible LLM service.
OPENAI_BASE_URL : str
    Base URL for OpenAI-compatible LLM service (e.g., LiteLLM proxy).
API_BASE_URL : str
    Next.js API base URL for search (e.g., http://localhost:3000).
INTERNAL_API_TOKEN : str
    Token for authenticating internal API calls.
LANGFUSE_PUBLIC_KEY : str
    Langfuse public key for authentication.
LANGFUSE_SECRET_KEY : str
    Langfuse secret key for authentication.

Optional Environment Variables
------------------------------
LANGFUSE_HOST : str
    Langfuse host URL (default: https://cloud.langfuse.com).
RESEARCH_MODEL : str
    LLM model name for research and evaluation (default: gemini-flash-lite).
EMBEDDING_MODEL : str
    Embedding model for RAGAS evaluation
    (default: sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2).

Output
------
Results are saved to: ../worker/evaluation/<dataset-name>/results/<date>-<seq>.json

Usage
-----
cd agent
uv run batch-eval --dataset-name research-evaluation  # Set dataset name
uv run batch-eval --run-name baseline-v1              # Set run name
uv run batch-eval --no-save                           # Don't save to file
uv run batch-eval --mode embedding                    # Use embedding search only
uv run batch-eval --all-modes                         # Compare all search modes
uv run batch-eval --limit 5 --dry-run                 # Preview 5 items
"""

import argparse
import asyncio
import json
import logging
import sys
import uuid
from datetime import datetime
from pathlib import Path

from langchain_huggingface import HuggingFaceEmbeddings
from langchain_openai import ChatOpenAI
from langfuse import Langfuse
from ragas.dataset_schema import SingleTurnSample
from ragas.embeddings import LangchainEmbeddingsWrapper
from ragas.llms import LangchainLLMWrapper
from ragas.metrics import Faithfulness, ResponseRelevancy

from buun_curator_agent.config import settings
from buun_curator_agent.graphs.research import create_research_graph
from buun_curator_agent.models.research import ResearchState, SearchMode

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


def check_required_env_vars() -> list[str]:
    """
    Check that all required environment variables are set.

    Returns
    -------
    list[str]
        List of missing environment variable names.
    """
    missing = []

    if not settings.openai_api_key or not settings.openai_api_key.get_secret_value():
        missing.append("OPENAI_API_KEY")

    if not settings.openai_base_url:
        missing.append("OPENAI_BASE_URL")

    if not settings.api_base_url:
        missing.append("API_BASE_URL")

    if not settings.internal_api_token:
        missing.append("INTERNAL_API_TOKEN")

    if not settings.langfuse_public_key:
        missing.append("LANGFUSE_PUBLIC_KEY")

    if not settings.langfuse_secret_key or not settings.langfuse_secret_key.get_secret_value():
        missing.append("LANGFUSE_SECRET_KEY")

    return missing

# Cached clients
_langfuse_client: Langfuse | None = None


def get_langfuse_client() -> Langfuse:
    """Get or create Langfuse client."""
    global _langfuse_client

    if _langfuse_client is not None:
        return _langfuse_client

    if not settings.langfuse_public_key or not settings.langfuse_secret_key:
        raise ValueError("LANGFUSE_PUBLIC_KEY and LANGFUSE_SECRET_KEY are required")

    _langfuse_client = Langfuse(
        public_key=settings.langfuse_public_key,
        secret_key=settings.langfuse_secret_key.get_secret_value(),
        host=settings.langfuse_host or None,
    )
    return _langfuse_client


def get_ragas_llm(trace_id: str | None = None) -> LangchainLLMWrapper:  # type: ignore[type-arg]
    """Get LLM wrapper for RAGAS evaluation."""
    extra_body = None
    if trace_id:
        extra_body = {
            "metadata": {
                "existing_trace_id": trace_id,
                "generation_name": "ragas-evaluation",
            }
        }

    llm = ChatOpenAI(
        model=settings.research_model or "gemini-flash-lite",
        temperature=0,
        api_key=settings.openai_api_key,  # type: ignore[arg-type]
        base_url=settings.openai_base_url or None,
        extra_body=extra_body,
    )

    return LangchainLLMWrapper(llm)


def get_ragas_embeddings() -> LangchainEmbeddingsWrapper:  # type: ignore[type-arg]
    """Get embeddings wrapper for RAGAS evaluation."""
    embeddings = HuggingFaceEmbeddings(model_name=settings.embedding_model)
    return LangchainEmbeddingsWrapper(embeddings)


def get_metrics(trace_id: str | None = None) -> list:
    """Get RAGAS metrics for evaluation."""
    llm = get_ragas_llm(trace_id=trace_id)
    embeddings = get_ragas_embeddings()

    return [
        Faithfulness(llm=llm, max_retries=3),
        ResponseRelevancy(llm=llm, embeddings=embeddings),
    ]


async def score_single(
    question: str,
    contexts: list[str],
    answer: str,
    trace_id: str | None = None,
) -> dict[str, float]:
    """Score a single Q&A sample using RAGAS metrics."""
    metrics = get_metrics(trace_id=trace_id)
    scores: dict[str, float] = {}

    sample = SingleTurnSample(
        user_input=question,
        retrieved_contexts=contexts,
        response=answer,
    )

    for metric in metrics:
        try:
            score = await metric.single_turn_ascore(sample)
            scores[metric.name] = score
            logger.info(f"RAGAS {metric.name}: {score:.3f}")
        except Exception as e:
            logger.error(f"Failed to compute {metric.name}: {e}")
            scores[metric.name] = -1.0

    return scores


async def run_research_for_item(
    question: str,
    trace_id: str,
    entry_context: str | None = None,
    search_mode: SearchMode = "planner",
) -> tuple[str, list[str]]:
    """
    Run research graph for a single evaluation item.

    Parameters
    ----------
    question : str
        Research question.
    trace_id : str
        Trace ID for Langfuse.
    entry_context : str | None
        Optional entry context.
    search_mode : SearchMode
        Search mode to use.

    Returns
    -------
    tuple[str, list[str]]
        Final answer and list of retrieved document contents.
    """
    initial_state: ResearchState = {
        "query": question,
        "entry_context": entry_context,
        "search_mode": search_mode,
        "plan": None,
        "retrieved_docs": [],
        "final_answer": "",
        "iteration": 0,
        "needs_more_info": False,
        "trace_id": trace_id,
        "session_id": None,
    }

    graph = create_research_graph()
    result = await graph.ainvoke(initial_state)

    final_answer = result.get("final_answer", "")
    retrieved_docs = result.get("retrieved_docs", [])
    contexts = [doc.content for doc in retrieved_docs if hasattr(doc, "content")]

    return final_answer, contexts


async def run_batch_evaluation(
    dataset_name: str,
    run_name: str | None = None,
    limit: int | None = None,
    dry_run: bool = False,
    search_mode: SearchMode = "planner",
) -> dict:
    """
    Run batch evaluation on a Langfuse dataset.

    Parameters
    ----------
    dataset_name : str
        Name of the Langfuse dataset to evaluate.
    run_name : str | None
        Name for this evaluation run. Auto-generated if not provided.
    limit : int | None
        Maximum number of items to evaluate. None for all items.
    dry_run : bool
        If True, only print items without running evaluation.
    search_mode : SearchMode
        Search mode to use for all items.

    Returns
    -------
    dict
        Summary of evaluation results.
    """
    langfuse = get_langfuse_client()

    # Fetch dataset
    logger.info(f"Fetching dataset: {dataset_name}")
    dataset = langfuse.get_dataset(dataset_name)
    items = list(dataset.items)
    logger.info(f"Found {len(items)} items in dataset")

    if limit:
        items = items[:limit]
        logger.info(f"Limited to {len(items)} items")

    if dry_run:
        logger.info("Dry run mode - printing items without evaluation")
        for i, item in enumerate(items):
            question = item.input.get("question", "")
            logger.info(f"[{i + 1}] {question[:80]}...")
        return {"status": "dry_run", "items_count": len(items)}

    # Generate run name
    if not run_name:
        run_name = f"batch-eval-{search_mode}-{datetime.now().strftime('%Y%m%d-%H%M%S')}"

    logger.info(f"Starting evaluation run: {run_name} (mode={search_mode})")

    results = []
    all_scores: dict[str, list[float]] = {}

    for i, item in enumerate(items):
        question = item.input.get("question", "")
        expected_answer = None
        if item.expected_output:
            expected_answer = item.expected_output.get("answer")

        logger.info(f"[{i + 1}/{len(items)}] Evaluating: {question[:50]}...")

        # Create trace for this evaluation item
        trace_id = str(uuid.uuid4())

        # Build run metadata from dataset item metadata
        run_metadata: dict = {"item_index": i, "search_mode": search_mode}
        if item.metadata:
            # Copy all metadata (exclude large nested objects)
            for key, value in item.metadata.items():
                if key not in ("source_entries",):  # Skip large nested objects
                    run_metadata[key] = value
            logger.debug(f"Item metadata keys: {list(item.metadata.keys())}")
        # Also check item.input for additional fields (e.g., reference, query_style)
        if item.input:
            for key in ("reference", "query_style", "query_length", "persona_name"):
                if key in item.input and key not in run_metadata:
                    run_metadata[key] = item.input[key]
            logger.debug(f"Item input keys: {list(item.input.keys())}")

        # Use Langfuse context manager to link trace to dataset item
        with item.run(
            run_name=run_name,
            run_metadata=run_metadata,
        ) as root_span:
            try:
                # Run research agent
                answer, contexts = await run_research_for_item(
                    question=question,
                    trace_id=trace_id,
                    search_mode=search_mode,
                )

                if not answer:
                    logger.warning(f"No answer generated for item {i + 1}")
                    continue

                logger.info(f"  Answer: {answer[:100]}...")
                logger.info(f"  Contexts: {len(contexts)} documents")

                # Calculate RAGAS scores
                scores = await score_single(
                    question=question,
                    contexts=contexts,
                    answer=answer,
                    trace_id=trace_id,
                )

                logger.info(f"  Scores: {scores}")

                # Update trace with input and output
                root_span.update(
                    input={"question": question},
                    output={"answer": answer, "contexts_count": len(contexts)},
                )

                # Record scores to Langfuse
                for metric_name, score_value in scores.items():
                    if score_value >= 0:
                        root_span.score(
                            name=metric_name,
                            value=float(score_value),  # Convert numpy types
                            comment=f"RAGAS {metric_name} score",
                        )
                        if metric_name not in all_scores:
                            all_scores[metric_name] = []
                        all_scores[metric_name].append(float(score_value))

                results.append({
                    "item_id": item.id,
                    "question": question,
                    "answer": answer[:200],
                    "contexts_count": len(contexts),
                    "scores": scores,
                    "expected_answer": expected_answer[:200] if expected_answer else None,
                })

            except Exception as e:
                logger.exception(f"Failed to evaluate item {i + 1}: {e}")
                results.append({
                    "item_id": item.id,
                    "question": question,
                    "error": str(e),
                })

    # Flush data to Langfuse
    langfuse.flush()

    # Calculate summary statistics
    summary = {
        "run_name": run_name,
        "dataset_name": dataset_name,
        "search_mode": search_mode,
        "total_items": len(items),
        "evaluated_items": len([r for r in results if "scores" in r]),
        "failed_items": len([r for r in results if "error" in r]),
        "average_scores": {},
    }

    for metric_name, scores_list in all_scores.items():
        if scores_list:
            avg = sum(scores_list) / len(scores_list)
            summary["average_scores"][metric_name] = round(avg, 4)
            logger.info(f"Average {metric_name}: {avg:.4f}")

    # Record run-level scores to Langfuse
    if all_scores and run_name:
        try:
            # Get dataset run via low-level API
            api = langfuse._resources.api if langfuse._resources else None
            if not api:
                raise RuntimeError("Langfuse API not available")
            dataset_run = api.datasets.get_run(
                dataset_name=dataset_name,
                run_name=run_name,
            )
            for metric_name, scores_list in all_scores.items():
                if scores_list:
                    avg = sum(scores_list) / len(scores_list)
                    langfuse.create_score(
                        name=f"avg_{metric_name}",
                        value=float(avg),
                        dataset_run_id=dataset_run.id,
                        comment=f"Average {metric_name} across {len(scores_list)} items",
                    )
                    logger.info(f"Recorded run-level score: avg_{metric_name} = {avg:.4f}")
            langfuse.flush()
        except Exception as e:
            logger.warning(f"Failed to record run-level scores: {e}")

    logger.info(f"Evaluation complete: {summary}")
    return summary


def main():
    """CLI entry point."""
    parser = argparse.ArgumentParser(
        description="Run batch evaluation on Langfuse dataset"
    )
    parser.add_argument(
        "--dataset-name",
        type=str,
        default="research-evaluation",
        help="Langfuse dataset name (default: research-evaluation)",
    )
    parser.add_argument(
        "--run-name",
        type=str,
        default=None,
        help="Name for this evaluation run (auto-generated if not provided)",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Maximum number of items to evaluate",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print items without running evaluation",
    )
    parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="Enable verbose logging",
    )
    parser.add_argument(
        "--no-save",
        action="store_true",
        help="Skip saving results to file",
    )
    parser.add_argument(
        "--mode",
        "-m",
        choices=["planner", "meilisearch", "embedding", "hybrid"],
        default="planner",
        help="Search mode (default: planner)",
    )
    parser.add_argument(
        "--all-modes",
        action="store_true",
        help="Run evaluation for all search modes sequentially",
    )

    args = parser.parse_args()

    # Determine results directory: ../worker/evaluation/<dataset-name>/results
    results_dir = Path("../worker/evaluation") / args.dataset_name / "results"

    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    # Check required environment variables
    missing_vars = check_required_env_vars()
    if missing_vars:
        print("Error: Missing required environment variables:", file=sys.stderr)
        for var in missing_vars:
            print(f"  - {var}", file=sys.stderr)
        print("\nSee script docstring for required environment variables.", file=sys.stderr)
        sys.exit(1)

    # Determine modes to run
    from typing import cast

    if args.all_modes:
        modes: list[SearchMode] = ["planner", "meilisearch", "embedding", "hybrid"]
    else:
        modes = [cast(SearchMode, args.mode)]

    try:
        all_summaries: list[dict] = []

        for mode in modes:
            if args.all_modes:
                print(f"\n{'#' * 60}")
                print(f"# Running evaluation with mode: {mode}")
                print(f"{'#' * 60}")

            summary = asyncio.run(
                run_batch_evaluation(
                    dataset_name=args.dataset_name,
                    run_name=args.run_name,
                    limit=args.limit,
                    dry_run=args.dry_run,
                    search_mode=mode,
                )
            )
            all_summaries.append(summary)

            print(f"\n{'=' * 60}")
            print(f"Evaluation Summary ({mode})")
            print(f"{'=' * 60}")
            for key, value in summary.items():
                print(f"  {key}: {value}")
            print(f"{'=' * 60}")

            # Save results to file
            if not args.no_save and not args.dry_run:
                results_dir.mkdir(parents=True, exist_ok=True)
                # Generate filename with date, mode and sequence number
                today = datetime.now().strftime("%Y-%m-%d")
                existing = list(results_dir.glob(f"{today}-{mode}-*.json"))
                seq = len(existing) + 1
                result_file = results_dir / f"{today}-{mode}-{seq}.json"

                result_data = {
                    "run_name": summary.get("run_name"),
                    "dataset_name": summary.get("dataset_name"),
                    "search_mode": mode,
                    "timestamp": datetime.now().isoformat(),
                    "total_items": summary.get("total_items"),
                    "evaluated_items": summary.get("evaluated_items"),
                    "failed_items": summary.get("failed_items"),
                    "average_scores": summary.get("average_scores"),
                }

                with open(result_file, "w", encoding="utf-8") as f:
                    json.dump(result_data, f, ensure_ascii=False, indent=2)
                print(f"\nResults saved to: {result_file}")

        # Print comparison summary if all modes were run
        if args.all_modes and len(all_summaries) > 1:
            print(f"\n{'=' * 60}")
            print("Mode Comparison Summary")
            print(f"{'=' * 60}")
            for s in all_summaries:
                mode_name = s.get("search_mode", "unknown")
                avg_scores = s.get("average_scores", {})
                scores_str = ", ".join(f"{k}={v:.4f}" for k, v in avg_scores.items())
                print(f"  {mode_name}: {scores_str}")
            print(f"{'=' * 60}")

    except KeyboardInterrupt:
        print("\n\nEvaluation cancelled by user.", file=sys.stderr)
        sys.exit(130)  # Standard exit code for SIGINT

    except Exception as e:
        logger.exception(f"Evaluation failed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
