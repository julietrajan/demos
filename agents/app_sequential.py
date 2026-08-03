"""
Sequential Travel Planner — Microsoft Agent Framework
Demonstrates SequentialBuilder orchestration:

  User Input
      ↓
  [1] DestinationResearcher  — picks the best destination
      ↓ (response only, via chain_only_agent_responses=True)
  [2] ItineraryPlanner       — builds a 5-day itinerary
      ↓ (response only)
  [3] BudgetAnalyst          — estimates costs & budget tips

Run with:
    streamlit run app_sequential.py
"""

import asyncio
import os

import streamlit as st
from azure.identity import AzureCliCredential, ChainedTokenCredential, DefaultAzureCredential
from dotenv import load_dotenv

from agent_framework import Agent, AgentResponse
from agent_framework.foundry import FoundryChatClient
from agent_framework.orchestrations import SequentialBuilder

load_dotenv()

# ── Pipeline stage metadata ───────────────────────────────────────────────────
PIPELINE_STAGES = [
    {
        "name": "DestinationResearcher",
        "icon": "🗺️",
        "label": "Destination Researcher",
        "step": "Stage 1",
        "description": "Selects the best destination for your preferences",
        "color": "#e8f4fd",
        "instructions": (
            "You are a travel destination expert.\n"
            "Given the user's travel preferences, interests, budget, and constraints, "
            "recommend the SINGLE best destination.\n\n"
            "Output strictly in this format:\n"
            "## Recommended Destination: [Name]\n"
            "**Why this destination:** [2-3 sentences]\n"
            "**Best time to visit:** [months / season]\n"
            "**Travel style match:** [adventure / culture / relaxation / etc.]\n"
            "**Top unmissable experience:** [one specific highlight]\n\n"
            "Be decisive. Do not list multiple options."
        ),
    },
    {
        "name": "ItineraryPlanner",
        "icon": "📅",
        "label": "Itinerary Planner",
        "step": "Stage 2",
        "description": "Creates a detailed day-by-day itinerary",
        "color": "#fef9e7",
        "instructions": (
            "You are a professional travel itinerary designer.\n"
            "Based on the recommended destination provided, create a detailed 5-day itinerary.\n\n"
            "Output strictly in this format:\n"
            "## 5-Day Itinerary: [Destination]\n"
            "For each day:\n"
            "### Day N — [Theme]\n"
            "- **Morning:** [activity]\n"
            "- **Afternoon:** [activity]\n"
            "- **Evening:** [activity + dinner recommendation]\n\n"
            "End with:\n"
            "## Essential Travel Tips\n"
            "- [4-5 practical tips specific to this destination]"
        ),
    },
    {
        "name": "BudgetAnalyst",
        "icon": "💰",
        "label": "Budget Analyst",
        "step": "Stage 3",
        "description": "Estimates costs and provides a budget breakdown",
        "color": "#eafaf1",
        "instructions": (
            "You are a travel budget specialist.\n"
            "Based on the 5-day itinerary provided, produce a realistic budget breakdown "
            "for one person in USD.\n\n"
            "Output strictly in this format:\n"
            "## Budget Breakdown: [Destination] — 5 Days\n"
            "| Category | Budget | Mid-range | Luxury |\n"
            "|---|---|---|---|\n"
            "| Flights (round-trip) | | | |\n"
            "| Accommodation (5 nights) | | | |\n"
            "| Food & Dining (5 days) | | | |\n"
            "| Activities & Entrance Fees | | | |\n"
            "| Local Transport | | | |\n"
            "| Miscellaneous | | | |\n"
            "| **TOTAL** | | | |\n\n"
            "## Money-Saving Tips\n"
            "- [3 specific cost-saving strategies for this destination]\n\n"
            "## Best Booking Advice\n"
            "- [When and where to book to get the best deals]"
        ),
    },
]


# ── Build pipeline (cached per session) ───────────────────────────────────────
@st.cache_resource(show_spinner="Connecting to Azure AI Foundry…")
def build_pipeline():
    """Initialise agents and assemble the SequentialBuilder workflow."""
    endpoint = os.environ.get("FOUNDRY_PROJECT_ENDPOINT", "")
    model = os.environ.get("FOUNDRY_MODEL", "gpt-5.4")

    if not endpoint:
        raise ValueError(
            "FOUNDRY_PROJECT_ENDPOINT is not set. "
            "Add it to your .env file or set it as an environment variable."
        )

    credential = ChainedTokenCredential(AzureCliCredential(), DefaultAzureCredential())

    # Each agent gets its own FoundryChatClient instance
    def make_client() -> FoundryChatClient:
        return FoundryChatClient(
            project_endpoint=endpoint,
            model=model,
            credential=credential,
        )

    agents = [
        Agent(
            client=make_client(),
            name=stage["name"],
            instructions=stage["instructions"],
        )
        for stage in PIPELINE_STAGES
    ]

    # SequentialBuilder wires agents in order.
    # chain_only_agent_responses=True  → each agent only receives the
    #   previous agent's response, not the whole conversation history.
    # intermediate_output_from="all_other" → surfaces every non-final
    #   agent's output so we can display per-stage results in the UI.
    workflow = SequentialBuilder(
        participants=agents,
        chain_only_agent_responses=True,
        intermediate_output_from="all_other",
    ).build()

    return workflow


# ── Run the pipeline and collect per-stage results ───────────────────────────
async def _run(workflow, user_input: str) -> list[dict]:
    """Await the workflow and collect an ordered list of per-agent outputs.

    get_intermediate_outputs() → stages 1..N-1  (event type "intermediate")
    get_outputs()              → stage N final   (event type "output")
    Combining both gives every stage in pipeline order.
    """
    result = await workflow.run(user_input)
    all_outputs = result.get_intermediate_outputs() + result.get_outputs()

    steps: list[dict] = []
    for i, output in enumerate(all_outputs):
        # Map output position back to the pipeline stage name
        stage_name = PIPELINE_STAGES[i]["name"] if i < len(PIPELINE_STAGES) else "assistant"
        text = output.text if isinstance(output, AgentResponse) else str(output or "")
        if text:
            steps.append({"agent": stage_name, "text": text})
    return steps


def run_pipeline(workflow, user_input: str) -> list[dict]:
    return asyncio.run(_run(workflow, user_input))


# ── Streamlit UI ──────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="Sequential Travel Planner",
    page_icon="🗺️",
    layout="wide",
)

st.title("🗺️ Sequential Travel Planner")
st.caption(
    "Powered by **Microsoft Agent Framework** · `SequentialBuilder` orchestration · Azure AI Foundry"
)

# ── Pipeline diagram ──────────────────────────────────────────────────────────
st.markdown("### Pipeline Architecture")

num = len(PIPELINE_STAGES)
cols = st.columns(num * 2 - 1)

for i, stage in enumerate(PIPELINE_STAGES):
    with cols[i * 2]:
        st.markdown(
            f"""
<div style="
    text-align:center;
    padding:14px 10px;
    border:1.5px solid #ccc;
    border-radius:10px;
    background:{stage['color']};
">
    <div style="font-size:2rem;">{stage['icon']}</div>
    <div style="font-size:0.65rem; color:#888; text-transform:uppercase; letter-spacing:0.05em;">{stage['step']}</div>
    <div style="font-weight:700; font-size:0.9rem; margin:4px 0;">{stage['label']}</div>
    <div style="font-size:0.75rem; color:#555;">{stage['description']}</div>
</div>""",
            unsafe_allow_html=True,
        )
    if i < num - 1:
        with cols[i * 2 + 1]:
            st.markdown(
                "<div style='text-align:center;font-size:1.8rem;padding-top:28px;color:#888;'>→</div>",
                unsafe_allow_html=True,
            )

st.markdown("")

# ── Code snippet callout ──────────────────────────────────────────────────────
with st.expander("📖 See the orchestration code", expanded=False):
    st.code(
        """\
from agent_framework.orchestrations import SequentialBuilder

workflow = SequentialBuilder(
    participants=[destination_agent, itinerary_agent, budget_agent],
    chain_only_agent_responses=True,   # each agent only sees the previous agent's output
    intermediate_output_from="all_other",  # surface all intermediate outputs
).build()

result = await workflow.run(user_input)
outputs = result.get_outputs()  # list of AgentResponse, one per stage
""",
        language="python",
    )

st.divider()

# ── User input ────────────────────────────────────────────────────────────────
st.markdown("### Describe your trip")

example_prompts = [
    "5-day adventure trip in Southeast Asia, mid-range budget (~$1,500), love hiking and street food",
    "Romantic European city break for 5 days, luxury budget, interested in art and fine dining",
    "Budget solo backpacking in South America for 5 days, love nature and local culture",
    "Family trip for 2 adults + 2 kids, beach destination, 5 days, moderate budget",
]

st.markdown("**Quick examples:**")
ex_cols = st.columns(2)
for idx, ex in enumerate(example_prompts):
    if ex_cols[idx % 2].button(ex, key=f"ex_{idx}", use_container_width=True):
        st.session_state["trip_input"] = ex

user_input: str = st.text_area(
    "Your travel preferences",
    value=st.session_state.get("trip_input", ""),
    placeholder=(
        "e.g. I want a 5-day adventure trip in Asia with a mid-range budget (~$1,500). "
        "I love hiking, street food, and local culture. Warm weather preferred."
    ),
    height=110,
    key="trip_input_area",
)

run_btn = st.button(
    "✈️ Plan My Trip",
    type="primary",
    disabled=not (user_input or "").strip(),
    use_container_width=True,
)

# ── Execute and display results ───────────────────────────────────────────────
if run_btn and (user_input or "").strip():
    # Initialise pipeline
    try:
        workflow = build_pipeline()
    except ValueError as exc:
        st.error(f"**Configuration error:** {exc}")
        st.stop()
    except Exception as exc:
        st.error(f"**Connection error:** {exc}")
        st.stop()

    st.divider()
    st.markdown("### Pipeline Results")

    # Stage-by-stage progress
    stage_placeholders = {}
    progress_cols = st.columns(num)
    for i, stage in enumerate(PIPELINE_STAGES):
        with progress_cols[i]:
            stage_placeholders[stage["name"]] = st.empty()
            stage_placeholders[stage["name"]].markdown(
                f"""<div style="
                    text-align:center;padding:8px;border-radius:6px;
                    background:#f0f0f0;color:#999;font-size:0.8rem;">
                    {stage['icon']} {stage['label']}<br/>⏳ Waiting…
                </div>""",
                unsafe_allow_html=True,
            )

    with st.spinner("Running sequential agent pipeline…"):
        try:
            steps = run_pipeline(workflow, user_input.strip())
        except Exception as exc:
            st.error(f"**Pipeline error:** {exc}")
            st.stop()

    # Update progress indicators to "Done"
    for stage in PIPELINE_STAGES:
        stage_placeholders[stage["name"]].markdown(
            f"""<div style="
                text-align:center;padding:8px;border-radius:6px;
                background:{stage['color']};font-size:0.8rem;border:1px solid #ccc;">
                {stage['icon']} {stage['label']}<br/>✅ Done
            </div>""",
            unsafe_allow_html=True,
        )

    st.markdown("")

    # Display per-stage outputs
    if steps:
        for step in steps:
            agent_name = step["agent"]
            meta = next(
                (s for s in PIPELINE_STAGES if s["name"] == agent_name),
                {"icon": "🤖", "label": agent_name, "step": "", "color": "#fff"},
            )
            with st.expander(
                f"{meta['icon']} {meta['step']} — {meta['label']}",
                expanded=True,
            ):
                st.markdown(step["text"])
    else:
        st.error(
            "Pipeline returned no output. "
            "Check that `intermediate_output_from='all_other'` is supported and that "
            "the agents completed successfully."
        )
