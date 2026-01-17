"""Common utilities for agent implementations."""

from ag_ui.core import RunAgentInput
from langchain_core.messages import BaseMessage, HumanMessage

from buun_curator_agent.config import settings
from buun_curator_agent.services.entry import EntryService


async def get_entry_context(input_data: RunAgentInput) -> str | None:
    """
    Fetch entry context from API if entryId is provided.

    Parameters
    ----------
    input_data : RunAgentInput
        Input data containing forwarded properties.

    Returns
    -------
    str | None
        Entry context as formatted string, or None if not available.
    """
    if not input_data.forwarded_props or not settings.api_base_url:
        return None

    entry_id = input_data.forwarded_props.get("entryId")
    if not entry_id:
        return None

    entry_service = EntryService(
        settings.api_base_url,
        settings.internal_api_token,
    )
    entry = await entry_service.get_entry(entry_id)
    if entry:
        return entry_service.build_context(entry)
    return None


def build_messages_from_input(input_data: RunAgentInput) -> list[BaseMessage]:
    """
    Build LangChain messages from input data.

    Parameters
    ----------
    input_data : RunAgentInput
        Input data containing conversation messages.

    Returns
    -------
    list[BaseMessage]
        List of LangChain messages (HumanMessage only for now).
    """
    messages: list[BaseMessage] = []
    if input_data.messages:
        for msg in input_data.messages:
            if msg.role == "user":
                content = msg.content if isinstance(msg.content, str) else str(msg.content)
                messages.append(HumanMessage(content=content))
    return messages
