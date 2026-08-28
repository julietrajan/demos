"""Streamlit chat client for the deployed Microsoft Foundry immigration agent.

Run with:
    az login
    streamlit run app_immigration.py
"""

import json
import os
from collections.abc import Iterator
from typing import Any

import requests
import streamlit as st
from azure.identity import DefaultAzureCredential
from dotenv import load_dotenv

load_dotenv()

AGENT_ENDPOINT = os.getenv(
    "IMMIGRATION_AGENT_ENDPOINT",
    "https://test-proj007-1-resource.services.ai.azure.com/api/projects/"
    "test-proj007-1/agents/immigration-agent/endpoint/protocols/openai/responses",
)
AGENT_IDENTITY = os.getenv(
    "IMMIGRATION_AGENT_IDENTITY",
    "7e82f8bb-79be-4d13-905e-54a727565de0",
)
AGENT_BLUEPRINT = os.getenv(
    "IMMIGRATION_AGENT_BLUEPRINT",
    "54afa59b-a84d-4d80-beeb-4573a3dd5600",
)
TOKEN_SCOPE = "https://ai.azure.com/.default"


@st.cache_resource
def get_credential() -> DefaultAzureCredential:
    """Reuse the Entra credential and its token cache across Streamlit reruns."""
    return DefaultAzureCredential()


def _error_message(response: requests.Response) -> str:
    try:
        body = response.json()
        detail = body.get("error", body) if isinstance(body, dict) else body
    except requests.JSONDecodeError:
        detail = response.text.strip() or response.reason

    if response.status_code in (401, 403):
        return (
            f"Foundry rejected the signed-in identity ({response.status_code}). "
            "Run 'az login' and ensure that identity has access to the Foundry "
            f"project. Details: {detail}"
        )
    return f"Foundry request failed ({response.status_code}): {detail}"


def stream_agent_response(
    prompt: str,
    previous_response_id: str | None = None,
) -> Iterator[tuple[str, str]]:
    """Yield (event kind, value) pairs from the OpenAI Responses SSE stream."""
    token = get_credential().get_token(TOKEN_SCOPE).token
    payload: dict[str, Any] = {"input": prompt, "stream": True}
    if previous_response_id:
        payload["previous_response_id"] = previous_response_id

    with requests.post(
        AGENT_ENDPOINT,
        params={"api-version": "v1"},
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
            "Accept": "text/event-stream",
        },
        json=payload,
        stream=True,
        timeout=(15, 300),
    ) as response:
        if not response.ok:
            raise RuntimeError(_error_message(response))

        for raw_line in response.iter_lines(decode_unicode=True):
            if not raw_line or raw_line.startswith(":"):
                continue

            data = raw_line.removeprefix("data:").strip()
            if data == "[DONE]":
                break

            try:
                event = json.loads(data)
            except json.JSONDecodeError:
                continue

            event_type = event.get("type")
            if event_type == "response.output_text.delta":
                yield "text", event.get("delta", "")
            elif event_type == "response.completed":
                response_id = event.get("response", {}).get("id")
                if response_id:
                    yield "response_id", response_id
            elif event_type in ("error", "response.failed"):
                raise RuntimeError(f"Agent stream failed: {event}")


st.set_page_config(
    page_title="Immigration Assistant",
    page_icon="🌐",
    layout="centered",
)

st.title("Immigration Assistant")
st.caption("Connected to the immigration-agent in Microsoft Foundry")

if "messages" not in st.session_state:
    st.session_state.messages = []
if "previous_response_id" not in st.session_state:
    st.session_state.previous_response_id = None

for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

if prompt := st.chat_input("Ask an immigration question"):
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    with st.chat_message("assistant"):
        placeholder = st.empty()
        chunks: list[str] = []
        response_id: str | None = None

        try:
            with st.spinner("Contacting the immigration agent..."):
                for event_kind, value in stream_agent_response(
                    prompt,
                    st.session_state.previous_response_id,
                ):
                    if event_kind == "text":
                        chunks.append(value)
                        placeholder.markdown("".join(chunks) + "▌")
                    elif event_kind == "response_id":
                        response_id = value
        except Exception as exc:
            placeholder.empty()
            st.error(str(exc))
        else:
            answer = "".join(chunks)
            placeholder.markdown(answer)
            st.session_state.messages.append(
                {"role": "assistant", "content": answer}
            )
            st.session_state.previous_response_id = response_id

with st.sidebar:
    st.subheader("Connection")
    st.text("Agent: immigration-agent")
    st.caption(f"Agent identity: {AGENT_IDENTITY}")
    st.caption(f"Agent blueprint: {AGENT_BLUEPRINT}")
    st.divider()
    st.caption("Authentication uses your current Microsoft Entra identity.")

    if st.button("Clear conversation", use_container_width=True):
        st.session_state.messages = []
        st.session_state.previous_response_id = None
        st.rerun()