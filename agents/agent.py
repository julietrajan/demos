"""
Travel Recommendation Agent using Microsoft Agent Framework
with Azure AI Foundry (FoundryChatClient).
"""

import os
from dotenv import load_dotenv
from agent_framework import Agent
from agent_framework.foundry import FoundryChatClient
from azure.identity import AzureCliCredential, DefaultAzureCredential, ChainedTokenCredential

load_dotenv()

_SYSTEM_INSTRUCTIONS = """
You are an expert travel advisor. When a user asks for travel recommendations,
you provide:
- Top destination suggestions based on their interests, budget, or travel style
- Best time to visit each destination
- Must-see attractions and local experiences
- Practical travel tips (visa, currency, safety, transport)
- Estimated budget range where helpful

Keep responses friendly, concise, and well-structured with clear sections.
If the user is vague, ask one focused clarifying question before recommending.
"""


def build_agent() -> Agent:
    """Create and return a configured travel recommendation Agent."""
    endpoint = os.environ.get("FOUNDRY_PROJECT_ENDPOINT", "")
    model = os.environ.get("FOUNDRY_MODEL", "gpt-5.4")

    if not endpoint:
        raise ValueError(
            "FOUNDRY_PROJECT_ENDPOINT is not set. "
            "Add it to your .env file or environment variables."
        )

    # Try AzureCliCredential first (local dev), fall back to DefaultAzureCredential
    credential = ChainedTokenCredential(
        AzureCliCredential(),
        DefaultAzureCredential(),
    )

    client = FoundryChatClient(
        project_endpoint=endpoint,
        model=model,
        credential=credential,
    )

    agent = Agent(
        client=client,
        name="TravelAdvisorAgent",
        instructions=_SYSTEM_INSTRUCTIONS,
    )
    return agent


async def get_recommendation(agent: Agent, user_message: str) -> str:
    """Send a message to the agent and return the response text."""
    result = await agent.run(user_message)
    return str(result)


async def stream_recommendation(agent: Agent, user_message: str):
    """Yield response chunks for streaming output."""
    async for chunk in agent.run(user_message, stream=True):
        if chunk.text:
            yield chunk.text
