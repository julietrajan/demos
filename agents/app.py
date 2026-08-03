"""
Streamlit UI for the Travel Recommendation Agent.

Run with:
    streamlit run app.py
"""

import asyncio
import streamlit as st
from agent import build_agent, stream_recommendation

# ── Page config ──────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="AI Travel Advisor",
    page_icon="✈️",
    layout="centered",
)

st.title("✈️ AI Travel Advisor")
st.caption("Powered by Microsoft Agent Framework · Azure AI Foundry")
st.markdown(
    "Ask me anything about travel — destinations, itineraries, tips, budgets, and more!"
)
st.divider()

# ── Agent initialisation (cached per session) ─────────────────────────────
@st.cache_resource(show_spinner="Connecting to Azure AI Foundry…")
def get_agent():
    return build_agent()

try:
    agent = get_agent()
except ValueError as exc:
    st.error(f"Configuration error: {exc}")
    st.stop()
except Exception as exc:
    st.error(f"Could not connect to Azure AI Foundry: {exc}")
    st.stop()

# ── Chat history ──────────────────────────────────────────────────────────
if "messages" not in st.session_state:
    st.session_state.messages = []

# Render existing messages
for msg in st.session_state.messages:
    with st.chat_message(msg["role"], avatar="🧳" if msg["role"] == "assistant" else None):
        st.markdown(msg["content"])

# ── User input ────────────────────────────────────────────────────────────
# Sidebar buttons store a pending prompt in session_state and call rerun().
# On the rerun, st.chat_input is empty but we pick up the pending prompt here.
chat_input = st.chat_input("Where would you like to travel?")
pending_prompt: str | None = st.session_state.pop("pending_prompt", None)
active_prompt = chat_input or pending_prompt

if active_prompt:
    # Sidebar buttons already appended the user message before rerun;
    # only append here when the prompt came from the text input.
    if chat_input:
        st.session_state.messages.append({"role": "user", "content": active_prompt})
        with st.chat_message("user"):
            st.markdown(active_prompt)

    # Stream agent response
    with st.chat_message("assistant", avatar="🧳"):
        placeholder = st.empty()
        # Accumulate chunks in a list to avoid global/closure scoping issues
        chunks: list[str] = []

        async def _stream_response() -> None:
            async for chunk in stream_recommendation(agent, active_prompt):
                chunks.append(chunk)
                placeholder.markdown("".join(chunks) + "▌")
            placeholder.markdown("".join(chunks))

        asyncio.run(_stream_response())
        full_response = "".join(chunks)

    st.session_state.messages.append(
        {"role": "assistant", "content": full_response}
    )

# ── Sidebar ───────────────────────────────────────────────────────────────
with st.sidebar:
    st.header("💡 Try asking…")
    examples = [
        "Best budget destinations in Southeast Asia for 2 weeks",
        "Family-friendly European cities to visit in summer",
        "Adventure travel ideas for solo travellers",
        "Hidden gems in South America off the beaten path",
        "What is the best time to visit Japan?",
    ]
    for example in examples:
        if st.button(example, use_container_width=True):
            # Append user message now so it shows on rerun, then queue
            # the prompt so the agent call fires on the same rerun.
            st.session_state.messages.append({"role": "user", "content": example})
            st.session_state["pending_prompt"] = example
            st.rerun()

    st.divider()
    if st.button("🗑️ Clear chat", use_container_width=True):
        st.session_state.messages = []
        st.rerun()
