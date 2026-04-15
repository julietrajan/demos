from dotenv import load_dotenv
import os
import asyncio

from autogen_agentchat.agents import AssistantAgent, UserProxyAgent
from autogen_agentchat.teams import RoundRobinGroupChat
from autogen_agentchat.ui import Console   # <-- async function, not a class
from autogen_ext.models.openai import AzureOpenAIChatCompletionClient

load_dotenv()

# Azure OpenAI model client
model_client = AzureOpenAIChatCompletionClient(
    azure_deployment=os.getenv("AZURE_OPENAI_CHAT_DEPLOYMENT"),  # deployment name
    model=os.getenv("AZURE_OPENAI_MODEL", "gpt-4o-mini"),
    api_version=os.getenv("AZURE_OPENAI_API_VERSION", "2024-10-21"),
    azure_endpoint=os.getenv("AZURE_OPENAI_ENDPOINT"),
    api_key=os.getenv("AZURE_OPENAI_API_KEY"),
)

# Agents
agent_a = AssistantAgent("AgentA", model_client=model_client,
                         system_message="Expert in travel recommendation")
agent_b = AssistantAgent("AgentB", model_client=model_client,
                         system_message="Expert in hotel recommendation.")
agent_c = AssistantAgent("AgentC", model_client=model_client,
                         system_message="Expert in food recommendation")
moderator = AssistantAgent("Moderator", model_client=model_client,
                           system_message="Synthesize all views and recommend the best option.")

user = UserProxyAgent("User", input_func=None)

team = RoundRobinGroupChat([agent_a, agent_b, agent_c, moderator])

async def main():
    # Pass the stream to Console; it returns the TaskResult
    result = await Console(team.run_stream(
        task="What is the best travel destination for a family vacation?"
    ))
    print("\n=== FINAL ===")
    print(result.final_message)
    await model_client.close()

asyncio.run(main())