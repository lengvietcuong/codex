from __future__ import annotations
import logging
import os

from dotenv import load_dotenv
import gradio as gr
from pydantic_ai.messages import ModelRequest, UserPromptPart
import supabase

from agent import codex_agent, Dependencies


load_dotenv()
supabase_client = supabase.Client(
    os.getenv("SUPABASE_URL"), os.getenv("SUPABASE_SERVICE_KEY")
)
dependencies = Dependencies(supabase_client=supabase_client)

# Set up logging with HTTP requests to avoid clutter
logging.basicConfig(level=logging.INFO, format="%(levelname)s - %(message)s")
logging.getLogger("httpx").disabled = True
logger = logging.getLogger(__name__)


# Async generator to stream responses from the agent
async def chat(user_prompt, chat_history, api_history):
    chat_history.extend(
        [{"role": "user", "content": user_prompt}, {"role": "assistant", "content": ""}]
    )
    user_message = ModelRequest(parts=[UserPromptPart(content=user_prompt)])
    api_history.append(user_message)

    async with codex_agent.run_stream(
        user_prompt,
        deps=dependencies,
        message_history=api_history[:-1],
    ) as result:
        partial_text = ""
        # Update the assistant message (which is the last in the list)
        async for chunk in result.stream_text(delta=True):
            partial_text += chunk
            chat_history[-1]["content"] = partial_text
            yield chat_history, chat_history, api_history

        # Append new messages from the API response (excluding duplicate user-prompt parts)
        new_messages = [
            message
            for message in result.new_messages()
            if not any(
                getattr(part, "part_kind", None) == "user-prompt"
                for part in message.parts
            )
        ]
        api_history.extend(new_messages)
    yield chat_history, chat_history, api_history


# Wrapper for the chat generator to be used as the submit handler
async def user_interaction(user_prompt, chat_history, api_history):
    async for updated_chat, state_chat, state_api in chat(
        user_prompt, chat_history, api_history
    ):
        yield updated_chat, state_chat, state_api


with gr.Blocks() as demo:
    gr.Markdown("# Codex")
    gr.Markdown(
        "Ask me anything about your favorite library, framework, or API. I currently know the documentation of Groq's API, Fireworks AI, and Unsloth. I'm also able to search in Stack Overflow."
    )

    chatbot = gr.Chatbot(type="messages")
    user_input = gr.Textbox(placeholder="Message Codex...", label="Your Message")
    state_chat = gr.State([])
    state_api = gr.State([])

    user_input.submit(
        user_interaction,
        inputs=[user_input, state_chat, state_api],
        outputs=[chatbot, state_chat, state_api],
    )

demo.launch()
