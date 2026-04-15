import os
from openai import AzureOpenAI

endpoint = "https://myfoundry007.cognitiveservices.azure.com/"
model_name = "gpt-5-chat"
deployment = "gpt-5-chat"

subscription_key = "dJj54yi2HhAC89Pjqxu6aP1HHswZbZR4uFAQNOLCAcWhxBCSJHJxJQQJ99CCACHYHv6XJ3w3AAAAACOG65RI"
api_version = "2024-12-01-preview"

client = AzureOpenAI(
    api_version=api_version,
    azure_endpoint=endpoint,
    api_key=subscription_key,
)

response = client.chat.completions.create(
    messages=[
        {
            "role": "system",
            "content": "You are an AI assistant who is going to answers questions related to ship wrecks. Add emojis in your response to make the conversation more engaging. If any questions other than ship wrecks are asked, you **MUST** disengage the conversation by saying Ahoy Captain!! I cant answer this. ",
        },
        {
            "role": "user",
            "content": "Help me understand about titanic in short",
        }
    ],
    max_completion_tokens=16384,
    model=deployment
)

print(response.choices[0].message.content)