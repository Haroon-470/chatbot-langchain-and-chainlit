import chainlit as cl
import asyncio
from langchain_ollama import ChatOllama
from langgraph.graph import StateGraph, END
from typing import TypedDict

# ---------------------------
# 1. Define the LangGraph State
# ---------------------------
class State(TypedDict):
    user_msg: str
    ai_msg: str

llm = ChatOllama(model="qwen2.5:0.5b", streaming=True)

# ---------------------------
# 2. Node: LLM Response
# ---------------------------
async def llm_node(state: State):
    user_message = state["user_msg"]

    # Stream tokens from the model
    final_answer = ""
    async for chunk in llm.astream(user_message):
        if chunk and hasattr(chunk, "content"):
            final_answer += chunk.content
    
    return {"ai_msg": final_answer}

# ---------------------------
# 3. Build the Graph
# ---------------------------
graph = StateGraph(State)
graph.add_node("llm", llm_node)
graph.set_entry_point("llm")
graph.set_finish_point("llm")

workflow = graph.compile()

# ---------------------------
# 4. Chainlit UI
# ---------------------------
@cl.on_chat_start
async def on_chat_start():
    await cl.Message("Hi Sir! How can I assist you today?").send()

@cl.on_message
async def on_message(message: cl.Message):
    print("User:", message.content)

    # Create a streaming message
    msg = cl.Message(content="")
    
    # Run graph stream
    async for event in workflow.astream({"user_msg": message.content}):
        if "llm" in event:
            chunk = event["llm"]["ai_msg"]
            if chunk:
                await msg.stream_token(chunk)

    await msg.send()
    #print("LLM Response:", msg.content)

@cl.on_stop
async def on_stop():
    print("The user wants to stop the task!")

@cl.on_chat_end
async def on_chat_end():
    print("The user disconnected!")
