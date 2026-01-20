# CopilotChat Architecture

This document describes the communication flow of the CopilotChat feature, from user input to response display.

## Architecture Overview

The system uses a three-layer architecture:

```text
┌─────────────────────┐     ┌─────────────────────┐     ┌─────────────────────┐
│   Frontend (React)  │────▶│  Next.js API Route  │────▶│  Python Agent       │
│   CopilotKit UI     │◀────│  CopilotKit Runtime │◀────│  (FastAPI + LLM)    │
└─────────────────────┘     └─────────────────────┘     └─────────────────────┘
```

### Why Route Through Next.js API?

The Next.js API layer serves as a secure proxy between the browser and the Python Agent:

| Concern       | Direct Browser → Agent        | Browser → Next.js → Agent |
| ------------- | ----------------------------- | ------------------------- |
| API Keys      | Exposed to client ❌          | Server-side only ✅       |
| Internal URLs | Visible to client ❌          | Hidden ✅                 |
| CORS          | Requires permissive policy ❌ | Server-to-server ✅       |
| Auth/Authz    | Duplicated logic ❌           | Centralized ✅            |

## Communication Flow

### Step-by-Step Process

```text
USER INPUT (Frontend)
       ↓
[1] ChatInput.send()
       ↓
[2] CopilotChat captures message
       ↓
[3] CopilotKit Provider sends POST /api/copilotkit
       ↓
[4] CopilotRuntime forwards to Python Agent
       ↓
[5] Agent fetches entry context via GET /api/entries/{id}
       ↓
[6] Agent calls LLM with context
       ↓
[7] SSE stream (AG-UI events) returns to frontend
       ↓
[8] CopilotChat renders response in real-time
       ↓
UI DISPLAY
```

### Sequence Diagram

```text
Browser          Next.js API        Python Agent        Next.js API       OpenAI
   │                  │                  │                  │               │
   │ POST /api/copilotkit                │                  │               │
   │ {messages, properties.entryId}      │                  │               │
   │─────────────────▶│                  │                  │               │
   │                  │ POST /ag-ui      │                  │               │
   │                  │─────────────────▶│                  │               │
   │                  │                  │ GET /api/entries/{id}            │
   │                  │                  │─────────────────▶│               │
   │                  │                  │◀─────────────────│               │
   │                  │                  │ (entry data)     │               │
   │                  │                  │                  │               │
   │                  │                  │ Chat Completion (streaming)      │
   │                  │                  │─────────────────────────────────▶│
   │                  │                  │◀─────────────────────────────────│
   │                  │◀─────────────────│                  │               │
   │                  │  SSE: TEXT_MESSAGE_CONTENT (chunks) │               │
   │◀─────────────────│                  │                  │               │
   │ (real-time display)                 │                  │               │
```

## Key Components

### Frontend Layer

#### ChatInput (`components/reader/chat-input.tsx`)

Captures user input and triggers the send action:

```typescript
const send = useCallback(() => {
  if (inProgress) return;
  onSend(text);  // Callback provided by CopilotChat
  setText("");
}, [inProgress, onSend, text]);
```

#### AssistantSidebar (`components/reader/assistant-sidebar.tsx`)

Renders the CopilotChat component with custom input:

```typescript
<CopilotChat
  labels={{ initial: "How can I help you understand this entry?" }}
  Input={(props) => <ChatInput {...props} />}
/>
```

#### CopilotKit Provider (`app/reader-layout.tsx`)

Wraps the application and configures the runtime endpoint:

```typescript
<CopilotKit
  runtimeUrl="/api/copilotkit"
  properties={{ entryId: currentArticleId }}
>
```

The `properties` object is forwarded to the agent, allowing it to fetch context for the current entry.

### Backend API Layer

#### CopilotKit Runtime (`app/api/copilotkit/route.ts`)

```typescript
const serviceAdapter = new ExperimentalEmptyAdapter();

const runtime = new CopilotRuntime({
  agents: {
    default: new HttpAgent({ url: `${AGENT_URL}/ag-ui` }),
  },
});

export const POST = async (req: NextRequest) => {
  const { handleRequest } = copilotRuntimeNextJSAppRouterEndpoint({
    runtime,
    serviceAdapter,
    endpoint: "/api/copilotkit",
  });
  return handleRequest(req);
};
```

#### Understanding serviceAdapter

The `serviceAdapter` defines how CopilotKit connects to an LLM:

| Adapter                    | Purpose                                  |
| -------------------------- | ---------------------------------------- |
| `OpenAIAdapter`            | Call OpenAI directly from Next.js        |
| `LangChainAdapter`         | Use LangChain in Next.js                 |
| `ExperimentalEmptyAdapter` | Delegate everything to an external agent |

This project uses `ExperimentalEmptyAdapter` because all LLM calls are handled by the Python Agent. The `HttpAgent` forwards requests to the agent's AG-UI endpoint.

### Agent Layer (Python)

#### AG-UI Endpoint (`agent/buun_curator_agent/routes/ag_ui.py`)

Implements the AG-UI protocol for CopilotKit integration:

```python
async def run_agent(input_data: RunAgentInput) -> AsyncGenerator[str, None]:
    # Extract entry ID from forwarded properties
    entry_id = input_data.forwarded_props.get("entryId")

    # Fetch entry context from Next.js API
    entry_service = EntryService(settings.api_base_url)
    entry = await entry_service.get_entry(entry_id)

    # Build system prompt with entry context
    system_prompt = "You are a helpful AI assistant..."
    if entry:
        system_prompt += f"\n\n{entry_service.build_context(entry)}"

    # Stream LLM response
    llm = ChatOpenAI(model=settings.research_model, streaming=True)
    async for chunk in llm.astream(messages):
        yield encoder.encode(TextMessageContentEvent(...))
```

#### EntryService (`agent/buun_curator_agent/services/entry.py`)

Fetches entry data from the Next.js API:

```python
class EntryService:
    async def get_entry(self, entry_id: str) -> Entry | None:
        url = f"{self.api_base_url}/api/entries/{entry_id}"
        async with httpx.AsyncClient() as client:
            response = await client.get(url, headers=self.headers)
            return Entry(**response.json())

    def build_context(self, entry: Entry) -> str:
        # Format entry as Markdown for system prompt
        return f"# {entry.title}\n\n{entry.content}"
```

## AG-UI Protocol Events

The agent streams responses using Server-Sent Events (SSE) with the AG-UI protocol:

| Event                  | Description                         |
| ---------------------- | ----------------------------------- |
| `RUN_STARTED`          | Agent execution begins              |
| `TEXT_MESSAGE_START`   | Message stream begins               |
| `TEXT_MESSAGE_CONTENT` | Text chunk (emitted multiple times) |
| `TEXT_MESSAGE_END`     | Message complete                    |
| `RUN_FINISHED`         | Agent execution complete            |

## File Reference

| Component         | File                                         | Purpose                  |
| ----------------- | -------------------------------------------- | ------------------------ |
| Chat Input        | `components/reader/chat-input.tsx`           | User input capture       |
| Assistant Sidebar | `components/reader/assistant-sidebar.tsx`    | Chat UI container        |
| Layout Provider   | `app/reader-layout.tsx`                      | CopilotKit context setup |
| Runtime Endpoint  | `app/api/copilotkit/route.ts`                | Request routing to agent |
| AG-UI Handler     | `agent/buun_curator_agent/routes/ag_ui.py`   | Agent protocol handler   |
| Entry Service     | `agent/buun_curator_agent/services/entry.py` | Entry context fetcher    |
| Agent Config      | `agent/buun_curator_agent/config.py`         | Environment settings     |

## Environment Variables

### Next.js

| Variable    | Description           | Default                 |
| ----------- | --------------------- | ----------------------- |
| `AGENT_URL` | Python agent base URL | `http://localhost:8000` |

### Python Agent

| Variable             | Description                          |
| -------------------- | ------------------------------------ |
| `OPENAI_API_KEY`     | OpenAI API key                       |
| `OPENAI_BASE_URL`    | Custom LLM endpoint (optional)       |
| `RESEARCH_MODEL`     | LLM model name                       |
| `API_BASE_URL`       | Next.js API URL for fetching entries |
| `INTERNAL_API_TOKEN` | Auth token for internal API calls    |
