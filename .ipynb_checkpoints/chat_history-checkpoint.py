import os
import chainlit as cl
from chainlit.types import ThreadDict
from chainlit.data.sql_alchemy import SQLAlchemyDataLayer

from langchain_ollama import ChatOllama
from langchain_core.messages import HumanMessage, AIMessage
import os
from dotenv import load_dotenv

# Load .env file at the top of your script
load_dotenv()
#from sql_code import app,State,db_schema,generate_query
print(f"🔍 Loaded DATABASE_URL: {os.getenv('DATABASE_URL')}")

# -----------------------------------
#  LLM
# -----------------------------------
llm = ChatOllama(model="qwen2.5:0.5b", streaming=True)


# -----------------------------------
#  Auth
# -----------------------------------
@cl.password_auth_callback
def auth_callback(username: str, password: str):
    if (username, password) == ("admin", "admin"):
        return cl.User(
            identifier="admin",
            metadata={"role": "admin", "provider": "credentials"}
        )
    return None


# -----------------------------------
#  Database
# -----------------------------------
@cl.data_layer
def get_data_layer():
    conninfo = os.getenv("DATABASE_URL")

    # if not conninfo:
    #     print("DATABASE_URL not found!")
    #     return None
    return SQLAlchemyDataLayer(conninfo=conninfo)
    # try:
    #     return SQLAlchemyDataLayer(conninfo=conninfo)
    # except Exception as e:
    #     print("SQLAlchemyDataLayer init error:", e)
    #     return None


# -----------------------------------
#  Resume Chat — Restore Chat History
# -----------------------------------
@cl.on_chat_resume
async def on_chat_resume(thread: ThreadDict):
    try:
        print("\n🔄 Resuming thread:", thread.get("id"))

        steps = thread.get("steps", [])
        restored_msgs = []

        for step in steps:
            step_type = step.get("type")
            user_text = step.get("input")
            ai_text = step.get("output")

            # user message
            if step_type == "user_message" and user_text:
                restored_msgs.append(HumanMessage(content=user_text.strip()))

            # assistant message
            elif step_type == "assistant_message" and ai_text:
                restored_msgs.append(AIMessage(content=ai_text.strip()))

        cl.user_session.set("chat_history", restored_msgs)

        print(f"🟢 Restored {len(restored_msgs)} historical messages.")

    except Exception as e:
        print("Error in on_chat_resume:", e)
        cl.user_session.set("chat_history", [])


# -----------------------------------
#  Start Chat
# -----------------------------------
@cl.on_chat_start
async def on_chat_start():
    cl.user_session.set("chat_history", [])
    await cl.Message(content="👋 Hello! I'm your AI assistant. How can I help you today?").send()


# -----------------------------------
#  Handle User Message
# -----------------------------------
@cl.on_message
async def on_message(msg: cl.Message):
    print("User:", msg.content)

    # Retrieve history
    history = cl.user_session.get("chat_history", [])

    # Build full LLM input
    messages = history + [HumanMessage(content=msg.content)]

    # Create blank assistant message for streaming
    assistant_msg = cl.Message(content="")
    await assistant_msg.send()

    # Stream tokens
    #async for chunk in llm.astream(messages):
    async for chunk in llm.astream(messages):
        token = chunk.content
        if token:
            await assistant_msg.stream_token(token)

    # Update complete final answer
    await assistant_msg.update()

    # Save new messages back into session
    history.append(HumanMessage(content=msg.content))
    history.append(AIMessage(content=assistant_msg.content))
    cl.user_session.set("chat_history", history)


# -----------------------------------
#  Events
# app
# -----------------------------------
@cl.on_stop
def on_stop():
    print("User stopped the response generation.")


@cl.on_chat_end
def on_chat_end():
    print("👋 User disconnected!")
