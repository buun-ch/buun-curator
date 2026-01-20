"""
LLM wrapper for LightRAG.

Provides an OpenAI-compatible LLM function for LightRAG using the
project's existing LLM configuration (OPENAI_BASE_URL, OPENAI_API_KEY).

The trace_id parameter can be bound using functools.partial() when creating
a LightRAG instance, allowing all LLM calls within that instance to share
the same Langfuse trace.
"""

import logging
import os
from typing import Any

logger = logging.getLogger(__name__)

# Default trace name for all LightRAG LLM calls
DEFAULT_TRACE_NAME = "lightrag"


def get_llm_config() -> dict[str, str]:
    """
    Get LLM configuration from environment.

    Returns
    -------
    dict[str, str]
        LLM configuration with model, api_key, and base_url.
    """
    return {
        "model": os.getenv("GRAPH_RAG_LLM_MODEL") or os.getenv("LLM_MODEL", "gpt-4o-mini"),
        "api_key": os.getenv("OPENAI_API_KEY", ""),
        "base_url": os.getenv("OPENAI_BASE_URL", ""),
    }


async def lightrag_llm_func(
    prompt: str,
    system_prompt: str | None = None,
    history_messages: list[dict[str, Any]] | None = None,
    keyword_extraction: bool = False,
    *,
    trace_id: str | None = None,
    **kwargs: Any,
) -> str:
    """
    LLM function for LightRAG using OpenAI-compatible API.

    This function is passed to LightRAG's llm_model_func parameter.
    It uses the project's existing OpenAI configuration via environment
    variables (OPENAI_BASE_URL, OPENAI_API_KEY, GRAPH_RAG_LLM_MODEL).

    Parameters
    ----------
    prompt : str
        The user prompt to send to the LLM.
    system_prompt : str | None
        Optional system prompt.
    history_messages : list[dict[str, Any]] | None
        Optional conversation history.
    keyword_extraction : bool
        Whether this is a keyword extraction call (may use different model).
    trace_id : str | None
        Langfuse trace ID for grouping LLM calls.
        Use functools.partial() to bind this when creating LightRAG instance.
    **kwargs : Any
        Additional parameters (max_tokens, temperature, etc.).

    Returns
    -------
    str
        The LLM response text.
    """
    from openai import AsyncOpenAI

    config = get_llm_config()
    model = config["model"]

    # For keyword extraction, could use a faster/cheaper model
    # Currently using the same model for all operations
    if keyword_extraction:
        logger.debug(f"Keyword extraction call using model: {model}")

    # Build client with project's configuration
    client_kwargs: dict[str, Any] = {"api_key": config["api_key"]}
    if config["base_url"]:
        client_kwargs["base_url"] = config["base_url"]

    client = AsyncOpenAI(**client_kwargs)

    # Build messages list
    messages: list[dict[str, str]] = []

    if system_prompt:
        messages.append({"role": "system", "content": system_prompt})

    if history_messages:
        messages.extend(history_messages)

    messages.append({"role": "user", "content": prompt})

    # Extract common parameters
    max_tokens = kwargs.get("max_tokens", 4096)
    temperature = kwargs.get("temperature", 0.0)

    # Set Langfuse metadata for tracing
    metadata: dict[str, Any] = {"trace_name": DEFAULT_TRACE_NAME}
    if trace_id:
        metadata["trace_id"] = trace_id
    extra_body: dict[str, Any] = {"metadata": metadata}

    logger.debug(
        f"LightRAG LLM call: model={model}, messages={len(messages)}, max_tokens={max_tokens}"
    )

    try:
        response = await client.chat.completions.create(
            model=model,
            messages=messages,  # type: ignore[arg-type]
            max_tokens=max_tokens,
            temperature=temperature,
            extra_body=extra_body,
        )

        result = response.choices[0].message.content or ""
        logger.debug(f"LLM response: {len(result)} chars")
        return result

    except Exception as e:
        logger.error(f"LLM call failed: {e}")
        raise
