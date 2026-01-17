"""Chat routes."""

import json
from collections.abc import AsyncGenerator

from fastapi import APIRouter, Request
from fastapi.responses import StreamingResponse
from langchain_core.messages import AIMessageChunk, HumanMessage
from langchain_openai import ChatOpenAI
from pydantic import BaseModel

from buun_curator_agent.config import settings

router = APIRouter()


class ChatRequest(BaseModel):
    """Chat request model."""

    message: str
    thread_id: str | None = None


class ChatResponse(BaseModel):
    """Chat response model."""

    message: str
    thread_id: str


@router.post("/chat")
async def chat(request: ChatRequest) -> ChatResponse:
    """
    Non-streaming chat endpoint.

    Parameters
    ----------
    request : ChatRequest
        Chat request containing the user message.

    Returns
    -------
    ChatResponse
        Chat response containing the AI message.
    """
    llm = ChatOpenAI(
        model=settings.research_model,
        api_key=settings.openai_api_key,
        base_url=settings.openai_base_url or None,
    )

    response = await llm.ainvoke([HumanMessage(content=request.message)])

    return ChatResponse(
        message=str(response.content),
        thread_id=request.thread_id or "default",
    )


@router.post("/chat/stream")
async def chat_stream(request: Request) -> StreamingResponse:
    """
    Streaming chat endpoint.

    Parameters
    ----------
    request : Request
        FastAPI request object.

    Returns
    -------
    StreamingResponse
        Server-sent events stream.
    """
    body = await request.json()
    message = body.get("message", "")

    async def generate() -> AsyncGenerator[str, None]:
        llm = ChatOpenAI(
            model=settings.research_model,
            api_key=settings.openai_api_key,
            base_url=settings.openai_base_url or None,
            streaming=True,
        )

        async for chunk in llm.astream([HumanMessage(content=message)]):
            if isinstance(chunk, AIMessageChunk) and chunk.content:
                data = json.dumps({"type": "text", "content": chunk.content})
                yield f"data: {data}\n\n"

        yield "data: [DONE]\n\n"

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
        },
    )
