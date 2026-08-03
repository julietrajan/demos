"""
Group Chat Travel Roundtable — Microsoft Agent Framework
Demonstrates GroupChatBuilder orchestration:

  A travel question enters a roundtable of 4 specialists.
  An orchestrator (selection_func) decides who speaks next.
  All agents share the FULL conversation — they can react to each
  other's suggestions before a Synthesizer produces the final plan.

  Round 0 → 🏔️ AdventureExpert
  Round 1 → 🏛️ CulturalGuide
  Round 2 → 💰 BudgetAdvisor
  Round 3 → ✍️  TravelSynthesizer  (terminal output)

Run with:
    streamlit run app_groupchat.py
"""

import asyncio
import os

import streamlit as st
from azure.identity import AzureCliCredential, ChainedTokenCredential, DefaultAzureCredential
from dotenv import load_dotenv

from agent_framework import Agent, AgentResponse
from agent_framework.orchestrations import GroupChatBuilder, GroupChatState

load_dotenv()

# ── Participants ──────────────────────────────────────────────────────────────
PARTICIPANTS = [
    {
        "name": "AdventureExpert",
        "icon": "🏔️",
        "label": "Adventure Expert",
        "color": "#eaf4fb",
        "border": "#aed6f1",
        "instructions": (
            "You are an adventure and outdoor travel specialist.\n"
            "When given a travel question, suggest exciting activities, outdoor experiences, "
            "unique adventures, and thrilling highlights for that destination.\n"
            "Keep your response to 3-5 bullet points. Be enthusiastic and specific.\n"
            "Read what other experts have already said and add ONLY what is new and complementary."
        ),
    },
    {
        "name": "CulturalGuide",
        "icon": "🏛️",
        "label": "Cultural Guide",
        "color": "#fef9e7",
        "border": "#f9e79f",
        "instructions": (
            "You are a cultural travel expert specialising in local experiences.\n"
            "When given a travel question, share insights on local cuisine, historical sites, "
            "festivals, authentic cultural experiences, and hidden neighbourhood gems.\n"
            "Keep your response to 3-5 bullet points. Be evocative and specific.\n"
            "Build on — and don't repeat — what other experts have already shared."
        ),
    },
    {
        "name": "BudgetAdvisor",
        "icon": "💰",
        "label": "Budget Advisor",
        "color": "#eafaf1",
        "border": "#a9dfbf",
        "instructions": (
            "You are a savvy travel budget specialist.\n"
            "When given a travel question, provide practical cost-saving tips, "
            "affordable alternatives, best-value accommodations, and money-smart strategies "
            "specific to the destination and activities already proposed.\n"
            "Keep your response to 3-5 bullet points with rough USD amounts where helpful.\n"
            "React to the adventure and cultural suggestions already in the conversation."
        ),
    },
    {
        "name": "TravelSynthesizer",
        "icon": "✍️",
        "label": "Travel Synthesizer",
        "color": "#f5eef8",
        "border": "#d2b4de",
        "instructions": (
            "You are the final travel planner who synthesizes expert opinions into a cohesive plan.\n"
            "Read ALL of the contributions from the Adventure Expert, Cultural Guide, "
            "and Budget Advisor in the conversation, then produce a polished, integrated travel plan.\n\n"
            "Output format:\n"
            "## Your Travel Plan: [Destination or Theme]\n"
            "### Top Experiences\n"
            "- [combine adventure + cultural highlights]\n\n"
            "### Cultural Immersion\n"
            "- [authentic local experiences]\n\n"
            "### Smart Budget Tips\n"
            "- [key money-saving strategies + rough cost]\n\n"
            "### Final Recommendation\n"
            "[2-3 sentence closing summary with an overall vibe/verdict]"
        ),
    },
]

# Speaker rotation: Adventure → Cultural → Budget → Synthesizer
_SPEAKER_ORDER = [p["name"] for p in PARTICIPANTS]


def _select_speaker(state: GroupChatState) -> str:
    """Round-robin speaker selection based on current_round."""
    idx = state.current_round % len(_SPEAKER_ORDER)
    return _SPEAKER_ORDER[idx]


# ── Build group chat pipeline (cached per session) ────────────────────────────
@st.cache_resource(show_spinner="Connecting to Azure AI Foundry…")
def build_groupchat():
    endpoint = os.environ.get("FOUNDRY_PROJECT_ENDPOINT", "")
    model = os.environ.get("FOUNDRY_MODEL", "gpt-5.4")

    if not endpoint:
        raise ValueError(
            "FOUNDRY_PROJECT_ENDPOINT is not set. "
            "Add it to your .env file or set it as an environment variable."
        )

    credential = ChainedTokenCredential(AzureCliCredential(), DefaultAzureCredential())

    def make_client():
        from agent_framework.foundry import FoundryChatClient
        return FoundryChatClient(
            project_endpoint=endpoint,
            model=model,
            credential=credential,
        )

    agents = [
        Agent(
            client=make_client(),
            name=p["name"],
            instructions=p["instructions"],
        )
        for p in PARTICIPANTS
    ]

    # GroupChatBuilder:
    #   selection_func  → who speaks next (round-robin here)
    #   max_rounds      → total turns (one per participant)
    #   output_from     → TravelSynthesizer is the terminal output
    #   intermediate_output_from → "all_other" surfaces all non-terminal agents
    workflow = GroupChatBuilder(
        participants=agents,
        selection_func=_select_speaker,
        max_rounds=len(PARTICIPANTS),
        output_from=["TravelSynthesizer"],
        intermediate_output_from="all_other",
    ).build()

    return workflow


# ── Run the group chat ────────────────────────────────────────────────────────
async def _run(workflow, user_input: str) -> list[dict]:
    """Run the group chat and return each agent's contribution in order."""
    result = await workflow.run(user_input)
    # intermediate → all except TravelSynthesizer; outputs → TravelSynthesizer
    all_outputs = result.get_intermediate_outputs() + result.get_outputs()

    steps: list[dict] = []
    for i, output in enumerate(all_outputs):
        p_name = PARTICIPANTS[i]["name"] if i < len(PARTICIPANTS) else "assistant"
        text = output.text if isinstance(output, AgentResponse) else str(output or "")
        if text:
            steps.append({"agent": p_name, "text": text})
    return steps


def run_groupchat(workflow, user_input: str) -> list[dict]:
    return asyncio.run(_run(workflow, user_input))


# ── Streamlit UI ──────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="Group Chat Travel Roundtable",
    page_icon="💬",
    layout="wide",
)

st.title("💬 Group Chat Travel Roundtable")
st.caption(
    "Powered by **Microsoft Agent Framework** · `GroupChatBuilder` orchestration · Azure AI Foundry"
)

# ── Key difference callout ────────────────────────────────────────────────────
st.info(
    "**Group Chat vs Sequential:** In Group Chat, every agent sees the **full shared conversation** — "
    "each expert reads and reacts to what the others said. "
    "In Sequential, each agent only receives the previous agent's output.",
    icon="💡",
)

# ── Participant cards ─────────────────────────────────────────────────────────
st.markdown("### Roundtable Participants")
cols = st.columns(len(PARTICIPANTS))
for col, p in zip(cols, PARTICIPANTS):
    with col:
        st.markdown(
            f"""<div style="
                text-align:center;padding:14px 10px;
                border:1.5px solid {p['border']};border-radius:10px;
                background:{p['color']};">
                <div style="font-size:2rem;">{p['icon']}</div>
                <div style="font-weight:700;font-size:0.9rem;margin:4px 0;">{p['label']}</div>
            </div>""",
            unsafe_allow_html=True,
        )

st.markdown("")

# ── Orchestration code snippet ────────────────────────────────────────────────
with st.expander("📖 See the orchestration code", expanded=False):
    st.code(
        """\
from agent_framework.orchestrations import GroupChatBuilder, GroupChatState

# Round-robin speaker selection
def select_speaker(state: GroupChatState) -> str:
    order = ["AdventureExpert", "CulturalGuide", "BudgetAdvisor", "TravelSynthesizer"]
    return order[state.current_round % len(order)]

workflow = GroupChatBuilder(
    participants=[adventure_agent, cultural_agent, budget_agent, synthesizer_agent],
    selection_func=select_speaker,      # who speaks each round
    max_rounds=4,                       # one round per participant
    output_from=["TravelSynthesizer"],  # terminal output source
    intermediate_output_from="all_other",  # surface the 3 specialist rounds
).build()

result = await workflow.run(user_input)
intermediate = result.get_intermediate_outputs()  # [Adventure, Cultural, Budget]
final        = result.get_outputs()               # [TravelSynthesizer]
""",
        language="python",
    )

st.divider()

# ── Input section ─────────────────────────────────────────────────────────────
st.markdown("### Ask the roundtable")

examples = [
    "Plan a 5-day adventure trip to Southeast Asia on a mid-range budget",
    "What's the best way to experience Japan's culture and food in one week?",
    "Suggest a luxury beach holiday that also offers cultural depth",
    "Best budget destinations in South America for a solo traveller",
]

st.markdown("**Quick examples:**")
ex_cols = st.columns(2)
for idx, ex in enumerate(examples):
    if ex_cols[idx % 2].button(ex, key=f"gc_ex_{idx}", use_container_width=True):
        st.session_state["gc_input"] = ex

user_input: str = st.text_area(
    "Your travel question",
    value=st.session_state.get("gc_input", ""),
    placeholder="e.g. Plan a 7-day trip to Japan combining adventure, culture, and good value",
    height=90,
    key="gc_input_area",
)

run_btn = st.button(
    "💬 Start Roundtable",
    type="primary",
    disabled=not (user_input or "").strip(),
    use_container_width=True,
)

# ── Execute and display ───────────────────────────────────────────────────────
if run_btn and (user_input or "").strip():
    try:
        workflow = build_groupchat()
    except ValueError as exc:
        st.error(f"**Configuration error:** {exc}")
        st.stop()
    except Exception as exc:
        st.error(f"**Connection error:** {exc}")
        st.stop()

    st.divider()
    st.markdown("### Roundtable Conversation")

    # Progress indicators
    prog_cols = st.columns(len(PARTICIPANTS))
    placeholders = {}
    for col, p in zip(prog_cols, PARTICIPANTS):
        with col:
            placeholders[p["name"]] = st.empty()
            placeholders[p["name"]].markdown(
                f"""<div style="text-align:center;padding:6px;border-radius:6px;
                    background:#f0f0f0;color:#999;font-size:0.8rem;">
                    {p['icon']} {p['label']}<br/>⏳ Waiting…</div>""",
                unsafe_allow_html=True,
            )

    with st.spinner("Roundtable in progress…"):
        try:
            steps = run_groupchat(workflow, user_input.strip())
        except Exception as exc:
            st.error(f"**Group chat error:** {exc}")
            st.stop()

    # Mark all done
    for p in PARTICIPANTS:
        placeholders[p["name"]].markdown(
            f"""<div style="text-align:center;padding:6px;border-radius:6px;
                background:{p['color']};border:1px solid {p['border']};font-size:0.8rem;">
                {p['icon']} {p['label']}<br/>✅ Done</div>""",
            unsafe_allow_html=True,
        )

    st.markdown("")

    if steps:
        for step in steps:
            p_meta = next(
                (p for p in PARTICIPANTS if p["name"] == step["agent"]),
                {"icon": "🤖", "label": step["agent"], "color": "#fff", "border": "#ccc"},
            )
            is_final = step["agent"] == "TravelSynthesizer"

            # Final synthesizer gets highlighted treatment
            if is_final:
                st.markdown("---")
                st.markdown(f"#### {p_meta['icon']} Final Synthesized Plan")

            with st.chat_message(
                name=p_meta["label"],
                avatar=p_meta["icon"],
            ):
                if is_final:
                    st.success(step["text"])
                else:
                    st.markdown(
                        f"<div style='border-left:4px solid {p_meta['border']};"
                        f"padding-left:10px;'>{step['text']}</div>",
                        unsafe_allow_html=True,
                    )
    else:
        st.error("No output received from the group chat. Check agent and workflow configuration.")
