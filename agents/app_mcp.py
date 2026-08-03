"""
Travel Advisor with MCP — Streamlit demo.

Demonstrates the Model Context Protocol (MCP) in a travel-recommendation
context. The Azure AI LLM decides which tools to call; every call is routed
through an MCP client to a local MCP server (travel_mcp_server.py) that
supplies structured travel data.

Architecture:
    User → Streamlit → Azure AI LLM ←→ MCP Client ←stdio→ MCP Server → Travel Tools

Run with:
    streamlit run app_mcp.py
"""

import asyncio
import json
import os
import sys
from pathlib import Path

import streamlit as st
from azure.ai.projects.aio import AIProjectClient
from azure.identity import AzureCliCredential, ChainedTokenCredential, DefaultAzureCredential
from dotenv import load_dotenv
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

load_dotenv()

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

SCRIPT_DIR = Path(__file__).parent
MCP_SERVER_SCRIPT = SCRIPT_DIR / "travel_mcp_server.py"

ENDPOINT = os.environ.get("FOUNDRY_PROJECT_ENDPOINT", "")
MODEL    = os.environ.get("FOUNDRY_MODEL", "gpt-4o")

SYSTEM_PROMPT = """
You are an expert travel advisor with access to real-time travel tools.
For every user request you MUST use the available tools to fetch destination,
weather, currency, safety, and cost data before composing your answer.

Always:
1. Call search_destinations to find suitable places.
2. Call get_weather_info, get_currency_info, get_travel_advisory, and
   estimate_trip_cost for each recommended destination.
3. Synthesise the tool results into a friendly, well-structured recommendation
   with clear sections: Destination, Best Time, Currency Tips, Safety, and Budget.

Never fabricate data — rely only on what the tools return.
""".strip()

# ---------------------------------------------------------------------------
# MCP tool metadata — displayed in the sidebar (mirrors travel_mcp_server.py)
# ---------------------------------------------------------------------------

MCP_TOOLS_META = [
    {"icon": "🔍", "name": "search_destinations",  "description": "Find destinations by travel style & daily budget"},
    {"icon": "🌤️", "name": "get_weather_info",      "description": "Best months to visit and climate notes"},
    {"icon": "💱", "name": "get_currency_info",     "description": "Currency code, rate vs USD, and money tips"},
    {"icon": "🛡️", "name": "get_travel_advisory",   "description": "Safety advisory level and key precautions"},
    {"icon": "💰", "name": "estimate_trip_cost",    "description": "Itemised cost estimate (flights, hotel, food…)"},
]

EXAMPLE_PROMPTS = [
    "Best beach destination under $80/day for 7 days",
    "Adventure trip to New Zealand — 10 days, mid-range budget",
    "Cultural tour of Japan in April, $100/day budget",
    "Safari in Tanzania — what does it cost and is it safe?",
]

# ---------------------------------------------------------------------------
# Core async agent loop (MCP + LLM)
# ---------------------------------------------------------------------------

async def run_travel_agent(user_message: str) -> tuple[str, list[dict]]:
    """
    Runs one turn of the travel agent.

    Spins up the MCP server as a subprocess, lists its tools, then runs an
    agentic LLM loop — routing every tool call through the MCP client —
    until the model produces a final answer.

    Returns:
        (answer_text, list_of_tool_call_dicts)
    """
    server_params = StdioServerParameters(
        command=sys.executable,
        args=[str(MCP_SERVER_SCRIPT)],
        env=None,  # inherit the current environment
    )

    tool_call_log: list[dict] = []

    credential = ChainedTokenCredential(AzureCliCredential(), DefaultAzureCredential())

    async with stdio_client(server_params) as (read_stream, write_stream):
        async with ClientSession(read_stream, write_stream) as mcp_session:
            await mcp_session.initialize()

            # Discover tools from the MCP server
            mcp_tools = (await mcp_session.list_tools()).tools

            # Convert MCP tool schemas → OpenAI function-calling format
            openai_tools = [
                {
                    "type": "function",
                    "function": {
                        "name": t.name,
                        "description": t.description or "",
                        "parameters": t.inputSchema,
                    },
                }
                for t in mcp_tools
            ]

            # AIProjectClient.get_openai_client() uses the same auth path as FoundryChatClient
            ai_project = AIProjectClient(endpoint=ENDPOINT, credential=credential)
            openai_client = ai_project.get_openai_client()

            messages: list = [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user",   "content": user_message},
            ]

            try:
                # Agentic loop (capped to prevent runaway calls)
                for _ in range(12):
                    response = await openai_client.chat.completions.create(
                        model=MODEL,
                        messages=messages,
                        tools=openai_tools,
                        tool_choice="auto",
                    )
                    choice = response.choices[0]

                    if choice.finish_reason == "tool_calls":
                        # Append the assistant's tool-call message to history
                        messages.append(choice.message.model_dump(exclude_unset=True))

                        # Execute each requested tool via the MCP server
                        for tc in choice.message.tool_calls:
                            args = json.loads(tc.function.arguments)

                            mcp_result = await mcp_session.call_tool(tc.function.name, args)

                            # Extract text from MCP content blocks
                            result_text = "\n".join(
                                item.text
                                for item in mcp_result.content
                                if hasattr(item, "text")
                            )

                            tool_call_log.append({
                                "tool":    tc.function.name,
                                "args":    args,
                                "result":  result_text,
                                "call_id": tc.id,
                            })

                            messages.append({
                                "role":         "tool",
                                "tool_call_id": tc.id,
                                "content":      result_text,
                            })
                    else:
                        return choice.message.content or "", tool_call_log
            finally:
                await openai_client.close()

    return "Agent reached the maximum tool-call limit without a final answer.", tool_call_log


def _agent_thread(user_message: str) -> tuple[str, list[dict]]:
    """Runs inside a dedicated OS thread so it owns a fresh event loop."""
    # ProactorEventLoop is required on Windows to spawn subprocesses from asyncio.
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        return loop.run_until_complete(run_travel_agent(user_message))
    finally:
        loop.close()


def run_agent_sync(user_message: str) -> tuple[str, list[dict]]:
    """Runs the async agent in a dedicated thread to avoid Streamlit loop conflicts."""
    import concurrent.futures
    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
        return pool.submit(_agent_thread, user_message).result()


# ---------------------------------------------------------------------------
# Streamlit UI helpers
# ---------------------------------------------------------------------------

def render_tool_call_expander(tool_calls: list[dict]) -> None:
    """Render an expander showing the MCP tool calls made for one turn."""
    if not tool_calls:
        return
    label = f"🔌 {len(tool_calls)} MCP tool call{'s' if len(tool_calls) != 1 else ''} used"
    with st.expander(label, expanded=False):
        for i, call in enumerate(tool_calls, 1):
            st.markdown(f"**{i}. `{call['tool']}`**")
            col_req, col_res = st.columns(2)
            with col_req:
                st.caption("Request (MCP → server)")
                st.code(json.dumps({"method": "tools/call", "params": {"name": call["tool"], "arguments": call["args"]}}, indent=2), language="json")
            with col_res:
                st.caption("Response (server → MCP)")
                try:
                    parsed = json.loads(call["result"])
                    st.code(json.dumps(parsed, indent=2), language="json")
                except (json.JSONDecodeError, TypeError):
                    st.code(call["result"], language="text")
            if i < len(tool_calls):
                st.divider()


def render_sidebar() -> None:
    with st.sidebar:
        st.header("🔌 Model Context Protocol")
        st.markdown(
            """
**MCP** is an open standard that lets AI models discover and call external
tools at runtime — without baking tool implementations into the model itself.

Each tool call is a structured JSON-RPC message sent over a transport
(here: **stdio**). The server is a completely independent Python process.
            """
        )

        st.subheader("Architecture")
        st.code(
            """\
User
 └─► Streamlit app
       └─► Azure AI LLM   (decides which tools to call)
             ↕  tool_calls / tool results  (MCP protocol)
           MCP Client
             ↕  JSON-RPC over stdio
           MCP Server  ← travel_mcp_server.py
             ├─ search_destinations
             ├─ get_weather_info
             ├─ get_currency_info
             ├─ get_travel_advisory
             └─ estimate_trip_cost""",
            language="text",
        )

        st.subheader("Available Tools")
        for t in MCP_TOOLS_META:
            st.markdown(f"**{t['icon']} `{t['name']}`**")
            st.caption(t["description"])

        st.divider()
        # Session stats
        total_calls = sum(
            len(msg.get("tool_calls", []))
            for msg in st.session_state.get("messages", [])
            if msg["role"] == "assistant"
        )
        st.metric("Total MCP tool calls this session", total_calls)


# ---------------------------------------------------------------------------
# Page setup
# ---------------------------------------------------------------------------

st.set_page_config(
    page_title="Travel Advisor — MCP Demo",
    page_icon="🗺️",
    layout="wide",
)

render_sidebar()

st.title("🗺️ Travel Advisor — MCP Demo")
st.caption("Azure AI · Model Context Protocol · travel_mcp_server.py")

if not ENDPOINT:
    st.error(
        "**FOUNDRY_PROJECT_ENDPOINT is not set.**  "
        "Add it (and optionally FOUNDRY_MODEL) to your `.env` file, then restart."
    )
    st.stop()

# ---------------------------------------------------------------------------
# Session state
# ---------------------------------------------------------------------------

if "messages" not in st.session_state:
    st.session_state.messages = []

# ---------------------------------------------------------------------------
# Example prompt quick-start buttons
# ---------------------------------------------------------------------------

if not st.session_state.messages:
    st.markdown("**Try one of these prompts:**")
    cols = st.columns(2)
    for idx, prompt in enumerate(EXAMPLE_PROMPTS):
        if cols[idx % 2].button(prompt, use_container_width=True):
            st.session_state["pending_prompt"] = prompt
            st.rerun()

st.divider()

# ---------------------------------------------------------------------------
# Render chat history
# ---------------------------------------------------------------------------

for msg in st.session_state.messages:
    avatar = "🧳" if msg["role"] == "assistant" else None
    with st.chat_message(msg["role"], avatar=avatar):
        st.markdown(msg["content"])
        render_tool_call_expander(msg.get("tool_calls", []))

# ---------------------------------------------------------------------------
# Handle new input (from chat box or example-prompt button)
# ---------------------------------------------------------------------------

chat_input     = st.chat_input("Where would you like to travel?")
pending_prompt = st.session_state.pop("pending_prompt", None)
active_prompt  = chat_input or pending_prompt

if active_prompt:
    # Show user bubble
    st.session_state.messages.append({"role": "user", "content": active_prompt, "tool_calls": []})
    with st.chat_message("user"):
        st.markdown(active_prompt)

    # Run the agent
    with st.chat_message("assistant", avatar="🧳"):
        with st.spinner("Consulting MCP tools…"):
            try:
                answer, tool_calls = run_agent_sync(active_prompt)
            except Exception as exc:
                # Unwrap anyio ExceptionGroup (Python 3.11+ TaskGroup failures)
                cause = exc.exceptions[0] if hasattr(exc, "exceptions") else exc
                answer = f"⚠️ Agent error: {type(cause).__name__}: {cause}"
                tool_calls = []

        st.markdown(answer)
        render_tool_call_expander(tool_calls)

    st.session_state.messages.append({
        "role":       "assistant",
        "content":    answer,
        "tool_calls": tool_calls,
    })
    st.rerun()
