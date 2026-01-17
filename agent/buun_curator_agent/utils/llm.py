"""LLM utility functions."""

from langchain_openai import ChatOpenAI

from buun_curator_agent.config import settings


def create_research_llm(
    trace_id: str | None = None,
    trace_name: str = "chat-research",
    generation_name: str | None = None,
    session_id: str | None = None,
    temperature: float = 0,
) -> ChatOpenAI:
    """
    Create a ChatOpenAI instance for research with optional tracing.

    Parameters
    ----------
    trace_id : str | None, optional
        Trace ID for Langfuse tracking (default: None).
    trace_name : str
        Trace name for Langfuse (default: "chat-research").
    generation_name : str | None, optional
        Generation name for individual LLM call (default: same as trace_name).
    session_id : str | None, optional
        Session ID for Langfuse session grouping (default: None).
    temperature : float
        Temperature for sampling (default: 0).

    Returns
    -------
    ChatOpenAI
        Configured LLM instance.
    """
    # Build metadata for Langfuse tracing
    # See: https://docs.litellm.ai/docs/observability/langfuse_integration
    extra_body = None
    if trace_id or session_id:
        metadata: dict[str, str] = {}
        if trace_id:
            metadata["trace_id"] = trace_id
            metadata["trace_name"] = trace_name
            metadata["generation_name"] = generation_name or trace_name
        if session_id:
            metadata["session_id"] = session_id
        extra_body = {"metadata": metadata}

    return ChatOpenAI(
        model=settings.research_model,
        api_key=settings.openai_api_key,
        base_url=settings.openai_base_url or None,
        temperature=temperature,
        extra_body=extra_body,
    )
